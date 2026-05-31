"""SQLite persistence for the AARI recruiting application."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "aari.db"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class Database:
    def __init__(self, path: str | Path = DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'candidate')),
                    phone TEXT DEFAULT '', title TEXT DEFAULT '', bio TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vacancies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    area TEXT NOT NULL, location TEXT NOT NULL, modality TEXT NOT NULL,
                    description TEXT NOT NULL, requirements TEXT NOT NULL,
                    skills TEXT NOT NULL, experience REAL DEFAULT 0,
                    status TEXT DEFAULT 'Activa', created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                    name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT DEFAULT '',
                    title TEXT DEFAULT '', skills TEXT DEFAULT '[]', cv_file TEXT DEFAULT '',
                    score REAL DEFAULT 0, status TEXT DEFAULT 'Pendiente',
                    analysis TEXT DEFAULT '', created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
                    vacancy_id INTEGER NOT NULL, status TEXT DEFAULT 'En revisión',
                    created_at TEXT NOT NULL, UNIQUE(candidate_id, vacancy_id),
                    FOREIGN KEY(candidate_id) REFERENCES candidates(id),
                    FOREIGN KEY(vacancy_id) REFERENCES vacancies(id)
                );
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
                    vacancy_id INTEGER NOT NULL, message TEXT NOT NULL,
                    status TEXT DEFAULT 'Pendiente', created_at TEXT NOT NULL,
                    FOREIGN KEY(candidate_id) REFERENCES candidates(id),
                    FOREIGN KEY(vacancy_id) REFERENCES vacancies(id)
                );
                CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
                    recipient TEXT NOT NULL, subject TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, FOREIGN KEY(candidate_id) REFERENCES candidates(id)
                );
                CREATE TABLE IF NOT EXISTS activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
                    detail TEXT NOT NULL, kind TEXT DEFAULT 'info', created_at TEXT NOT NULL
                );
                """
            )
            self._seed(connection)

    def _seed(self, connection: sqlite3.Connection) -> None:
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        password = generate_password_hash("Demo1234")
        connection.executemany(
            "INSERT INTO users(name,email,password_hash,role,phone,title,bio,created_at) VALUES(?,?,?,?,?,?,?,?)",
            [
                ("Administrador AARI", "admin@aari.pe", password, "admin", "+51 900 000 001", "Talent Manager", "", now()),
                ("Carlos Mendoza", "candidato@aari.pe", password, "candidate", "+51 987 654 321", "Product Designer", "Diseñador orientado a productos digitales.", now()),
            ],
        )
        vacancies = [
            ("Senior Product Designer", "Diseño", "Lima, Perú", "Híbrido", "Diseña experiencias digitales de alto impacto.", "Portafolio, investigación UX y trabajo colaborativo.", ["Figma", "UX Research", "Design Systems"], 4),
            ("Full Stack Developer", "Tecnología", "Remoto", "Remoto", "Construye productos web escalables.", "Experiencia con Python, Flask, SQL y JavaScript.", ["Python", "Flask", "SQL", "JavaScript"], 3),
            ("Data Scientist AI", "Tecnología", "Lima, Perú", "Híbrido", "Desarrolla modelos para decisiones de talento.", "Python, SQL y Machine Learning.", ["Python", "SQL", "Machine Learning"], 3),
            ("Marketing Strategist", "Marketing", "Arequipa, Perú", "Presencial", "Lidera campañas basadas en datos.", "Analítica, estrategia y comunicación.", ["Analytics", "Strategy", "Communication"], 2),
        ]
        connection.executemany(
            "INSERT INTO vacancies(title,area,location,modality,description,requirements,skills,experience,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [(a, b, c, d, e, f, json.dumps(g), h, now()) for a, b, c, d, e, f, g, h in vacancies],
        )
        user_id = connection.execute("SELECT id FROM users WHERE role='candidate'").fetchone()[0]
        candidates = [
            (user_id, "Carlos Mendoza", "candidato@aari.pe", "+51 987 654 321", "Product Designer", ["Figma", "UX Research", "Design Systems"], "", 92, "Preseleccionado", "Perfil sólido con experiencia relevante."),
            (None, "María Quispe", "maria.quispe@example.com", "+51 987 111 222", "Data Scientist", ["Python", "SQL", "Machine Learning"], "maria_cv.pdf", 89, "Preseleccionado", "Alta compatibilidad técnica y experiencia demostrable."),
            (None, "Diego Torres", "diego.torres@example.com", "+51 987 333 444", "Backend Developer", ["Python", "Flask", "SQL"], "diego_cv.pdf", 78, "En evaluación", "Buen encaje técnico; validar experiencia en despliegue."),
        ]
        connection.executemany(
            "INSERT INTO candidates(user_id,name,email,phone,title,skills,cv_file,score,status,analysis,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(a, b, c, d, e, json.dumps(f), g, h, i, j, now()) for a, b, c, d, e, f, g, h, i, j in candidates],
        )
        candidate_id = connection.execute("SELECT id FROM candidates WHERE user_id=?", (user_id,)).fetchone()[0]
        connection.executemany(
            "INSERT INTO applications(candidate_id,vacancy_id,status,created_at) VALUES(?,?,?,?)",
            [(candidate_id, 1, "Entrevista", now()), (candidate_id, 2, "En revisión", now())],
        )
        connection.execute(
            "INSERT INTO invitations(candidate_id,vacancy_id,message,status,created_at) VALUES(?,?,?,?,?)",
            (candidate_id, 1, "Tu perfil fue seleccionado para una entrevista con el equipo de Diseño.", "Pendiente", now()),
        )
        self.add_activity("Base inicial creada", "AARI cargó los datos de demostración.", "ai", connection)

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connect() as connection:
            return int(connection.execute(sql, params).lastrowid)

    def add_activity(self, action: str, detail: str, kind: str = "info", connection: sqlite3.Connection | None = None) -> None:
        values = (action, detail, kind, now())
        if connection:
            connection.execute("INSERT INTO activities(action,detail,kind,created_at) VALUES(?,?,?,?)", values)
        else:
            self.execute("INSERT INTO activities(action,detail,kind,created_at) VALUES(?,?,?,?)", values)

    def vacancies(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM vacancies ORDER BY id DESC")
        for row in rows:
            row["skills"] = json.loads(row["skills"])
        return rows

    def candidates(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM candidates ORDER BY score DESC, id")
        for row in rows:
            row["skills"] = json.loads(row["skills"])
        return rows

    def candidate_for_user(self, user_id: int) -> dict[str, Any] | None:
        row = self.one("SELECT * FROM candidates WHERE user_id=?", (user_id,))
        if row:
            row["skills"] = json.loads(row["skills"])
        return row
