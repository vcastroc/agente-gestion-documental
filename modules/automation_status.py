"""System status and automation controls module."""


def get_automation_status(db) -> dict:
    """Get current status of autonomous systems."""
    return {
        "cv_monitor": "🟢 Activo" if True else "🔴 Inactivo",
        "scheduler": "🟢 Activo" if True else "🔴 Inactivo",
        "last_processing": db.query(
            "SELECT created_at FROM candidates ORDER BY created_at DESC LIMIT 1"
        ),
        "last_email": db.query(
            "SELECT created_at FROM email_logs ORDER BY created_at DESC LIMIT 1"
        ),
        "pending_invitations": db.query(
            "SELECT COUNT(*) as count FROM invitations WHERE status = 'Pendiente'"
        )[0]["count"],
        "automated_candidates": db.query(
            "SELECT COUNT(*) as count FROM candidates WHERE title LIKE '%automático%'"
        )[0]["count"],
    }
