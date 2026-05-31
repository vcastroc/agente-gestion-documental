"""SQLite persistence layer for vacancies, candidates and autonomous runs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from utils import now_iso

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "database" / "cv_agent.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    area TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    required_experience REAL NOT NULL DEFAULT 0,
    required_skills TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ANALYZED',
    total_candidates INTEGER NOT NULL DEFAULT 0,
    average_score REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (vacancy_id) REFERENCES vacancies(id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    career TEXT,
    experience_years REAL NOT NULL DEFAULT 0,
    skills TEXT NOT NULL,
    languages TEXT NOT NULL,
    certifications TEXT NOT NULL,
    projects TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    score REAL NOT NULL,
    similarity_score REAL NOT NULL,
    skill_score REAL NOT NULL,
    experience_score REAL NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    status TEXT NOT NULL,
    selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (process_id) REFERENCES processes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);
"""


class Database:
    """Small repository class that keeps SQL away from the UI."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def create_vacancy(self, vacancy: dict[str, Any]) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO vacancies
                    (title, area, description, requirements,
                     required_experience, required_skills, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vacancy["title"],
                    vacancy["area"],
                    vacancy["description"],
                    vacancy["requirements"],
                    float(vacancy["required_experience"]),
                    json.dumps(vacancy["required_skills"], ensure_ascii=False),
                    now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def list_vacancies(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM vacancies ORDER BY id DESC"
            ).fetchall()
        return [self._decode_vacancy(row) for row in rows]

    def get_vacancy(self, vacancy_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM vacancies WHERE id = ?", (vacancy_id,)
            ).fetchone()
        return self._decode_vacancy(row) if row else None

    def create_process(self, vacancy_id: int) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO processes (vacancy_id, created_at) VALUES (?, ?)",
                (vacancy_id, now_iso()),
            )
            return int(cursor.lastrowid)

    def update_process_summary(self, process_id: int) -> None:
        with self.connect() as connection:
            summary = connection.execute(
                """
                SELECT COUNT(*) AS total, COALESCE(AVG(score), 0) AS average
                FROM candidates WHERE process_id = ?
                """,
                (process_id,),
            ).fetchone()
            connection.execute(
                """
                UPDATE processes
                SET total_candidates = ?, average_score = ?
                WHERE id = ?
                """,
                (summary["total"], round(summary["average"], 2), process_id),
            )

    def save_candidate(self, process_id: int, result: dict[str, Any]) -> int:
        profile = result["profile"]
        analysis = result["analysis"]
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO candidates (
                    process_id, file_name, name, email, phone, career,
                    experience_years, skills, languages, certifications,
                    projects, raw_text, score, similarity_score, skill_score,
                    experience_score, matched_skills, missing_skills, status,
                    selected, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    process_id,
                    profile["file_name"],
                    profile["name"],
                    profile["email"],
                    profile["phone"],
                    profile["career"],
                    profile["experience_years"],
                    json.dumps(profile["skills"], ensure_ascii=False),
                    json.dumps(profile["languages"], ensure_ascii=False),
                    json.dumps(profile["certifications"], ensure_ascii=False),
                    json.dumps(profile["projects"], ensure_ascii=False),
                    profile["raw_text"],
                    analysis["score"],
                    analysis["similarity_score"],
                    analysis["skill_score"],
                    analysis["experience_score"],
                    json.dumps(analysis["matched_skills"], ensure_ascii=False),
                    json.dumps(analysis["missing_skills"], ensure_ascii=False),
                    analysis["status"],
                    int(analysis["selected"]),
                    now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def list_processes(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT p.*, v.title AS vacancy_title, v.area AS vacancy_area,
                       (SELECT COUNT(*) FROM email_logs e
                        JOIN candidates c ON c.id = e.candidate_id
                        WHERE c.process_id = p.id AND e.status = 'ENVIADO') AS sent_emails
                FROM processes p
                JOIN vacancies v ON v.id = p.vacancy_id
                ORDER BY p.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_candidates(self, process_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM candidates WHERE process_id = ? ORDER BY score DESC, id",
                (process_id,),
            ).fetchall()
        return [self._decode_candidate(row) for row in rows]

    def update_selection(self, process_id: int, selected_ids: list[int]) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE candidates SET selected = 0, status = 'NO SELECCIONADO' WHERE process_id = ?",
                (process_id,),
            )
            if selected_ids:
                placeholders = ",".join("?" for _ in selected_ids)
                connection.execute(
                    f"UPDATE candidates SET selected = 1, status = 'PRESELECCIONADO' "
                    f"WHERE process_id = ? AND id IN ({placeholders})",
                    (process_id, *selected_ids),
                )

    def add_email_log(
        self,
        candidate_id: int,
        recipient: str,
        subject: str,
        body: str,
        status: str,
        error_message: str = "",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO email_logs
                    (candidate_id, recipient, subject, body, status,
                     error_message, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    recipient,
                    subject,
                    body,
                    status,
                    error_message,
                    now_iso(),
                ),
            )

    def list_email_logs(self, process_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*, c.name AS candidate_name
                FROM email_logs e
                JOIN candidates c ON c.id = e.candidate_id
                WHERE c.process_id = ?
                ORDER BY e.id DESC
                """,
                (process_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _decode_vacancy(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["required_skills"] = json.loads(result["required_skills"])
        return result

    @staticmethod
    def _decode_candidate(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for field in (
            "skills",
            "languages",
            "certifications",
            "projects",
            "matched_skills",
            "missing_skills",
        ):
            result[field] = json.loads(result[field])
        result["selected"] = bool(result["selected"])
        return result
