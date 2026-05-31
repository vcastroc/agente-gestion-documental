"""Action module: creates and sends personalized interview invitations."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any


@dataclass
class SMTPConfig:
    sender_email: str
    app_password: str
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    simulation_mode: bool = True


def build_invitation(
    candidate_name: str,
    vacancy_title: str,
    interview_date: str,
    interview_time: str,
) -> tuple[str, str]:
    subject = f"Invitación a entrevista - {vacancy_title}"
    body = f"""Estimado/a {candidate_name}:

Ha sido preseleccionado/a para la vacante de {vacancy_title}.

Deseamos invitarle a una entrevista:
Fecha: {interview_date}
Hora: {interview_time}

Por favor, responda a este correo para confirmar su asistencia.

Saludos cordiales,
Equipo de Selección
"""
    return subject, body


def send_email(
    config: SMTPConfig,
    recipient: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send an email or simulate delivery for a classroom demonstration."""
    if not recipient:
        return {"status": "ERROR", "error": "El candidato no tiene correo registrado."}
    if config.simulation_mode:
        return {"status": "SIMULADO", "error": ""}
    if not config.sender_email or not config.app_password:
        return {"status": "ERROR", "error": "Complete el correo remitente y la contraseña de aplicación."}

    message = EmailMessage()
    message["From"] = config.sender_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=20) as server:
            if config.use_tls:
                server.starttls()
            server.login(config.sender_email, config.app_password)
            server.send_message(message)
        return {"status": "ENVIADO", "error": ""}
    except Exception as exc:  # SMTP providers return actionable messages at runtime.
        return {"status": "ERROR", "error": str(exc)}
