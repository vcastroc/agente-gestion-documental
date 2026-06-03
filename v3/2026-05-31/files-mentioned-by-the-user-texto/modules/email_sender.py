import os
import smtplib
from email.message import EmailMessage

from modules.database import (
    guardar_evento_historial,
    marcar_correo_enviado,
    obtener_borradores_correo,
    obtener_correos_en_cola,
)


def generar_mensaje(nombre, cargo, fecha, hora):
    return (
        f"Hola {nombre},\n\n"
        f"Tu perfil ha sido preseleccionado para la vacante de {cargo}. "
        f"Te invitamos a una entrevista el {fecha or 'día por confirmar'} "
        f"a las {hora or 'hora por confirmar'}.\n\n"
        "Saludos,\nEquipo de Recursos Humanos"
    )


def obtener_configuracion_smtp():
    config = {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("SMTP_FROM", "").strip(),
        "use_tls": os.environ.get("SMTP_USE_TLS", "1") == "1",
        "use_ssl": os.environ.get("SMTP_USE_SSL", "0") == "1",
    }
    config["from_email"] = config["from_email"] or config["user"]
    return config


def smtp_configurado():
    config = obtener_configuracion_smtp()
    return bool(config["host"] and config["from_email"])


def enviar_correo_smtp(destinatario, asunto, mensaje):
    config = obtener_configuracion_smtp()
    if not config["host"] or not config["from_email"]:
        raise RuntimeError("Configura SMTP_HOST y SMTP_FROM o SMTP_USER antes de enviar correos.")

    email = EmailMessage()
    email["From"] = config["from_email"]
    email["To"] = destinatario
    email["Subject"] = asunto
    email.set_content(mensaje)

    smtp_class = smtplib.SMTP_SSL if config["use_ssl"] else smtplib.SMTP
    with smtp_class(config["host"], config["port"], timeout=20) as server:
        if config["use_tls"] and not config["use_ssl"]:
            server.starttls()
        if config["user"]:
            server.login(config["user"], config["password"])
        server.send_message(email)


def enviar_borradores_correo(vacante_id=None):
    enviados, errores = 0, []
    for correo in obtener_borradores_correo(vacante_id):
        try:
            enviar_correo_smtp(correo["destinatario"], correo["asunto"], correo["mensaje"])
            marcar_correo_enviado(correo["id"])
            enviados += 1
        except Exception as error:
            errores.append(f"{correo['destinatario']}: {error}")
    if enviados:
        guardar_evento_historial("Correos enviados", f"{enviados} correo(s) enviados por SMTP")
    if errores:
        guardar_evento_historial("Error de correo", " | ".join(errores)[:1000])
    return {"enviados": enviados, "errores": errores}


def enviar_correos_en_cola(vacante_id=None):
    enviados, errores = 0, []
    for correo in obtener_correos_en_cola(vacante_id):
        try:
            enviar_correo_smtp(correo["destinatario"], correo["asunto"], correo["mensaje"])
            marcar_correo_enviado(correo["id"])
            enviados += 1
        except Exception as error:
            errores.append(f"{correo['destinatario']}: {error}")
    if enviados:
        guardar_evento_historial("Correos enviados", f"{enviados} correo(s) enviados por SMTP desde el worker")
    if errores:
        guardar_evento_historial("Error de correo", " | ".join(errores)[:1000])
        raise RuntimeError(" | ".join(errores)[:500])
    return {"enviados": enviados, "errores": errores}
