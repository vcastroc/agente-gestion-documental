import json
import re

from modules.database import _rows, obtener_usuario_por_id
from modules.ollama_client import _enabled, _model, _post_json


BASE_PROMPT = """
Eres RecruitBot, un asistente experto en recursos humanos.

Tu funcion es ayudar a reclutadores a consultar informacion de candidatos, vacantes, entrevistas y rankings.

Responde siempre en español.

Responde de forma breve, profesional y precisa.

Si la informacion existe en la base de datos, usala para responder.

Usa solo la intencion del mensaje actual.

No continues consultas anteriores si el mensaje actual es un saludo o agradecimiento.

No inventes candidatos ni datos inexistentes.

Si no hay suficientes datos, dilo claramente.

Cuando sea posible, explica por que un candidato es recomendado.
"""

SALUDO_RESPUESTA = (
    "Hola, soy RecruitBot 🤖. Puedo ayudarte a consultar candidatos, vacantes, rankings, "
    "entrevistas y decisiones del agente."
)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalizar(text):
    text = _clean(text).lower()
    replacements = str.maketrans("áéíóúüñ", "aeiouun")
    return text.translate(replacements)


def detectar_intencion(mensaje):
    text = _normalizar(mensaje)
    if not text:
        return "vacio"

    saludos_exactos = {
        "hola", "buenas", "buenos dias", "buen dia", "buenas tardes", "buenas noches",
        "gracias", "ok", "okay", "entendido", "listo", "perfecto", "dale",
    }
    if text in saludos_exactos:
        return "saludo"

    if any(text.startswith(prefix) for prefix in ("hola ", "buenas ", "gracias ", "ok ", "entendido ")):
        if not any(word in text for word in ("candidato", "ranking", "vacante", "entrevista", "aprobado", "rechazado")):
            return "saludo"

    rrhh_keywords = (
        "top", "mejor candidato", "ranking", "vacante", "entrevista", "candidato",
        "aprobado", "rechazado", "postulante", "python", "experiencia", "requisito",
        "seleccion", "preguntas", "decision", "agente",
    )
    if any(keyword in text for keyword in rrhh_keywords):
        return "consulta_rrhh"
    return "general"


def _lines(title, rows, formatter, empty="Sin datos registrados."):
    if not rows:
        return f"{title}: {empty}"
    return title + ":\n" + "\n".join(f"- {formatter(row)}" for row in rows)


def _contexto_admin():
    vacantes = _rows(
        """SELECT id,titulo,empresa,area,carreras_objetivo,estado,fecha_entrevista,hora_entrevista
        FROM vacantes ORDER BY estado='Activa' DESC, id DESC LIMIT 12"""
    )
    ranking = _rows(
        """SELECT a.compatibilidad,a.estado,a.justificacion,a.accion_sugerida,c.nombre,c.correo,
        v.titulo AS vacante,d.estado AS decision_rrhh
        FROM analisis a JOIN candidatos c ON c.id=a.candidato_id
        JOIN vacantes v ON v.id=a.vacante_id
        LEFT JOIN decisiones_rrhh d ON d.candidato_id=c.id AND d.vacante_id=v.id
        ORDER BY a.compatibilidad DESC, a.id DESC LIMIT 12"""
    )
    entrevistas = _rows(
        """SELECT co.destinatario,co.estado,v.titulo AS vacante,v.fecha_entrevista,v.hora_entrevista
        FROM correos co LEFT JOIN vacantes v ON v.id=co.vacante_id
        WHERE co.estado IN ('Enviado','Confirmada','Rechazada')
        ORDER BY co.id DESC LIMIT 10"""
    )
    conteos = _rows(
        """SELECT v.titulo,
        COUNT(p.id) AS postulantes,
        SUM(CASE WHEN d.estado='Aprobado' THEN 1 ELSE 0 END) AS aprobados,
        SUM(CASE WHEN d.estado='Rechazado' THEN 1 ELSE 0 END) AS rechazados
        FROM vacantes v
        LEFT JOIN postulaciones p ON p.vacante_id=v.id
        LEFT JOIN candidatos c ON c.usuario_id=p.usuario_id
        LEFT JOIN decisiones_rrhh d ON d.candidato_id=c.id AND d.vacante_id=v.id
        GROUP BY v.id ORDER BY v.id DESC LIMIT 10"""
    )
    return "\n\n".join([
        _lines("Vacantes", vacantes, lambda r: f"#{r['id']} {r['titulo']} ({r['empresa']}) area={r.get('area') or '-'} carreras={r.get('carreras_objetivo') or '-'} estado={r['estado']} entrevista={r.get('fecha_entrevista') or '-'} {r.get('hora_entrevista') or ''}"),
        _lines("Ranking", ranking, lambda r: f"{r['nombre']} para {r['vacante']}: {r['compatibilidad']}%, IA={r['estado']}, RRHH={r.get('decision_rrhh') or 'Pendiente'}, razon={_clean(r.get('justificacion')) or '-'}"),
        _lines("Entrevistas e invitaciones", entrevistas, lambda r: f"{r['destinatario']} - {r['vacante'] or '-'} - {r['estado']} - {r.get('fecha_entrevista') or 'por definir'} {r.get('hora_entrevista') or ''}"),
        _lines("Conteo por vacante", conteos, lambda r: f"{r['titulo']}: postulantes={r['postulantes'] or 0}, aprobados={r['aprobados'] or 0}, rechazados={r['rechazados'] or 0}"),
    ])


def _contexto_candidato(user_id):
    usuario = obtener_usuario_por_id(user_id) or {}
    postulaciones = _rows(
        """SELECT p.estado,p.compatibilidad,p.recomendacion_ia,v.titulo,v.empresa,v.area
        FROM postulaciones p JOIN vacantes v ON v.id=p.vacante_id
        WHERE p.usuario_id=? ORDER BY p.id DESC LIMIT 10""",
        (user_id,),
    )
    vacantes = _rows(
        """SELECT titulo,empresa,area,carreras_objetivo,estado FROM vacantes
        WHERE estado='Activa' ORDER BY id DESC LIMIT 10"""
    )
    invitaciones = _rows(
        """SELECT co.estado,co.asunto,v.titulo AS vacante,v.fecha_entrevista,v.hora_entrevista
        FROM correos co LEFT JOIN vacantes v ON v.id=co.vacante_id
        WHERE co.destinatario=? AND co.estado IN ('Enviado','Confirmada','Rechazada')
        ORDER BY co.id DESC LIMIT 8""",
        (usuario.get("correo"),),
    )
    return "\n\n".join([
        f"Usuario candidato: {usuario.get('nombre','-')} carrera={usuario.get('carrera') or '-'} ciudad={usuario.get('ciudad') or '-'}",
        _lines("Mis postulaciones", postulaciones, lambda r: f"{r['titulo']} ({r['empresa']}): estado={r['estado']}, compatibilidad={r.get('compatibilidad')}, recomendacion IA={r.get('recomendacion_ia') or '-'}"),
        _lines("Vacantes activas", vacantes, lambda r: f"{r['titulo']} ({r['empresa']}) area={r.get('area') or '-'} carreras={r.get('carreras_objetivo') or '-'}"),
        _lines("Mis invitaciones", invitaciones, lambda r: f"{r['vacante'] or '-'} - {r['estado']} - {r.get('fecha_entrevista') or 'por definir'} {r.get('hora_entrevista') or ''}"),
    ])


def _contexto_publico():
    vacantes = _rows(
        "SELECT titulo,empresa,area,carreras_objetivo,estado FROM vacantes WHERE estado='Activa' ORDER BY id DESC LIMIT 8"
    )
    return _lines(
        "Vacantes publicas activas",
        vacantes,
        lambda r: f"{r['titulo']} ({r['empresa']}) area={r.get('area') or '-'} carreras={r.get('carreras_objetivo') or '-'}",
    )


def construir_contexto(role=None, user_id=None):
    if role == "admin":
        return _contexto_admin()
    if role == "candidato" and user_id:
        return _contexto_candidato(user_id)
    return _contexto_publico()


def respuesta_fallback(message, contexto):
    text = message.lower()
    if "mejor candidato" in text or "top" in text:
        rows = _rows(
            """SELECT c.nombre,v.titulo AS vacante,a.compatibilidad,a.estado
            FROM analisis a JOIN candidatos c ON c.id=a.candidato_id
            JOIN vacantes v ON v.id=a.vacante_id
            ORDER BY a.compatibilidad DESC LIMIT 5"""
        )
        if rows:
            return "Mejores candidatos:\n" + "\n".join(
                f"- {r['nombre']} para {r['vacante']}: {r['compatibilidad']}% ({r['estado']})" for r in rows
            )
    if "python" in text:
        rows = _rows(
            """SELECT c.nombre,v.titulo AS vacante,a.compatibilidad
            FROM analisis a JOIN candidatos c ON c.id=a.candidato_id
            JOIN vacantes v ON v.id=a.vacante_id
            WHERE lower(a.habilidades_encontradas) LIKE '%python%'
            ORDER BY a.compatibilidad DESC LIMIT 8"""
        )
        if rows:
            return "Candidatos con Python:\n" + "\n".join(
                f"- {r['nombre']} ({r['vacante']}): {r['compatibilidad']}%" for r in rows
            )
    if "preguntas" in text and "entrevista" in text:
        return (
            "Preguntas sugeridas:\n"
            "- Describe un proyecto relevante para esta vacante.\n"
            "- Que tecnologias o herramientas dominas mejor?\n"
            "- Como resolverias un problema critico en el puesto?\n"
            "- Que experiencia previa se relaciona directamente con los requisitos?"
        )
    return (
        "Puedo ayudarte con candidatos, vacantes, rankings, entrevistas y decisiones. "
        "Ahora mismo resumire con la informacion disponible: " + contexto[:700]
    )


def responder_recruitbot(message, history=None, role=None, user_id=None):
    message = _clean(message)
    if not message:
        return "Escribe una pregunta sobre candidatos, vacantes, ranking o entrevistas."
    intent = detectar_intencion(message)
    if intent == "saludo":
        return SALUDO_RESPUESTA
    history = history or []
    contexto = construir_contexto(role, user_id)
    prompt = f"""{BASE_PROMPT}

ROL DEL USUARIO: {role or 'publico'}

INTENCION DEL MENSAJE ACTUAL: {intent}

CONTEXTO DE BASE DE DATOS:
{contexto}

HISTORIAL RECIENTE SOLO COMO REFERENCIA, NO COMO INTENCION:
{json.dumps(history[-4:], ensure_ascii=False)}

PREGUNTA:
{message}
"""
    if _enabled():
        try:
            response = _post_json("/api/chat", {
                "model": _model(),
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.2},
            })
            answer = _clean(response["message"]["content"])
            if answer:
                return answer
        except Exception:
            pass
    return respuesta_fallback(message, contexto)
