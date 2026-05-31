"""Autonomous automation system for CV processing and invitation sending."""

import logging
from pathlib import Path
from uuid import uuid4

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .database import Database, now
from .extractor import extract_profile
from .analyzer import analyze_profile

logger = logging.getLogger("AARI_Automation")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s: %(message)s"
)


class CVUploadHandler(FileSystemEventHandler):
    """Automatically processes new CV uploads."""

    def __init__(self, db: Database, vacancy_id: int | None = None):
        self.db = db
        self.vacancy_id = vacancy_id

    def on_created(self, event):
        if event.is_file and self._is_cv_file(event.src_path):
            self._process_cv(Path(event.src_path))

    @staticmethod
    def _is_cv_file(path: str) -> bool:
        return Path(path).suffix.lower() in {".pdf", ".docx", ".txt"}

    def _process_cv(self, path: Path):
        """Process CV file and extract profile."""
        try:
            logger.info(f"🔄 Processing CV: {path.name}")
            profile = extract_profile(path)
            
            vacancy = self.vacancy_id or self.db.vacancies()[0]["id"]
            vacancy_data = self.db.one(
                "SELECT * FROM vacancies WHERE id=?", (vacancy,)
            )

            if not vacancy_data:
                logger.warning(f"❌ No vacancy found (ID: {vacancy})")
                return

            result = analyze_profile(profile, vacancy_data)
            
            candidate_id = self.db.execute(
                """INSERT INTO candidates
                (name, email, phone, title, skills, cv_file, score, status, analysis, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    profile["name"],
                    profile["email"] or f"{uuid4().hex[:8]}@sin-correo.local",
                    profile["phone"],
                    "Importado automáticamente",
                    str(profile["skills"]),
                    path.name,
                    result["score"],
                    result["status"],
                    result["summary"],
                    now(),
                ),
            )

            self.db.add_activity(
                "✅ CV procesado automáticamente",
                f"{profile['name']} - Score: {result['score']}%",
                "success",
            )
            logger.info(f"✅ CV processed: {profile['name']} (Score: {result['score']}%)")

            if result["score"] >= 75:
                logger.info(f"🎯 Candidate '{profile['name']}' meets criteria for auto-invitation")
                self.db.execute(
                    """INSERT INTO invitations (candidate_id, vacancy_id, message, status, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        candidate_id,
                        vacancy,
                        f"Automático - Score: {result['score']}%",
                        "Pendiente",
                        now(),
                    ),
                )

        except Exception as exc:
            logger.error(f"❌ Error processing {path.name}: {exc}")
            self.db.add_activity(
                "❌ Error en procesamiento",
                f"{path.name}: {str(exc)}",
                "danger",
            )


def start_cv_monitor(uploads_dir: Path, db: Database):
    """Start watching for new CV uploads."""
    handler = CVUploadHandler(db)
    observer = Observer()
    observer.schedule(handler, str(uploads_dir), recursive=False)
    observer.start()
    logger.info(f"🚀 CV Monitor started - watching {uploads_dir}")
    return observer


def process_pending_invitations(db: Database):
    """Send pending invitations to candidates with high scores."""
    pending = db.query(
        """SELECT i.*, c.email, c.name, v.title
        FROM invitations i
        JOIN candidates c ON c.id = i.candidate_id
        JOIN vacancies v ON v.id = i.vacancy_id
        WHERE i.status = 'Pendiente' AND c.score >= 75
        LIMIT 10"""
    )

    for invitation in pending:
        try:
            logger.info(f"📧 Sending invitation to {invitation['email']} for {invitation['title']}")
            
            from .email_sender import send_invitation
            result = send_invitation(
                {"email": invitation["email"], "name": invitation["name"]},
                {"title": invitation["title"]},
            )

            db.execute(
                "UPDATE invitations SET status = ? WHERE id = ?",
                (result["status"], invitation["id"]),
            )

            db.add_activity(
                "📧 Invitación automática enviada",
                f"{invitation['name']} - {invitation['title']}",
                "success",
            )
            logger.info(f"✅ Invitation sent to {invitation['email']}")

        except Exception as exc:
            logger.error(f"❌ Error sending invitation: {exc}")


def generate_daily_report(db: Database) -> dict:
    """Generate automated daily performance report."""
    today_activities = db.query(
        """SELECT * FROM activities
        WHERE created_at >= datetime('now', 'start of day')
        ORDER BY id DESC"""
    )

    candidates_today = db.query(
        """SELECT COUNT(*) as count FROM candidates
        WHERE created_at >= datetime('now', 'start of day')"""
    )[0]["count"]

    emails_today = db.query(
        """SELECT COUNT(*) as count FROM email_logs
        WHERE created_at >= datetime('now', 'start of day')"""
    )[0]["count"]

    high_scores = db.query(
        """SELECT COUNT(*) as count FROM candidates
        WHERE score >= 75 AND created_at >= datetime('now', 'start of day')"""
    )[0]["count"]

    report = {
        "date": now(),
        "cvs_processed": candidates_today,
        "emails_sent": emails_today,
        "high_score_candidates": high_scores,
        "activities": today_activities,
    }

    logger.info(
        f"📊 Daily Report: {candidates_today} CVs, {emails_today} emails, {high_scores} qualified"
    )

    return report
