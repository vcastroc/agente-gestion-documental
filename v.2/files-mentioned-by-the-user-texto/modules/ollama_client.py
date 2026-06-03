import json
import os
import re
from urllib.error import URLError
from urllib.request import Request, urlopen


def _enabled():
    return os.environ.get("OLLAMA_ENABLED", "0") == "1"


def _base_url():
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _model():
    return os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")


def _post_json(path, payload):
    request = Request(
        f"{_base_url()}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=float(os.environ.get("OLLAMA_TIMEOUT", "30"))) as response:
        return json.loads(response.read().decode("utf-8"))


def obtener_estado_ollama():
    if not _enabled():
        return {"activo": False, "estado": "Deshabilitado", "modelo": _model()}
    try:
        with urlopen(f"{_base_url()}/api/version", timeout=2) as response:
            version = json.loads(response.read().decode("utf-8")).get("version", "desconocida")
        return {"activo": True, "estado": f"Activo · v{version}", "modelo": _model()}
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return {"activo": False, "estado": "No disponible", "modelo": _model()}


def anonimizar_texto_cv(texto):
    texto = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[CORREO OMITIDO]", texto)
    texto = re.sub(r"(?:\+?\d[ \t()-]*){7,15}", "[TELEFONO OMITIDO]", texto)
    return re.sub(r"(?im)^\s*(?:direccion|domicilio|address)\s*[:\-].*$", "[DIRECCION OMITIDA]", texto)


def detectar_habilidades_semanticas(texto_cv, vacante, habilidades_requeridas):
    if not _enabled() or not habilidades_requeridas:
        return []
    schema = {
        "type": "object",
        "properties": {
            "habilidades_detectadas": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["habilidades_detectadas"],
    }
    texto_anonimo = anonimizar_texto_cv(texto_cv)
    prompt = f"""
Actua como analista de reclutamiento. Tu tarea es comparar un CV contra una lista cerrada de habilidades requeridas.

Reglas:
- Devuelve solo habilidades que aparezcan en la lista exacta de HABILIDADES REQUERIDAS.
- Puedes reconocer sinonimos, equivalencias profesionales y evidencia clara del CV.
- No inventes habilidades.
- Si no existe evidencia suficiente en el CV, no incluyas esa habilidad.
- Responde solo JSON segun el esquema.

VACANTE:
Titulo: {vacante.get('titulo', '') if isinstance(vacante, dict) else ''}
Area: {vacante.get('area', '') if isinstance(vacante, dict) else ''}
Descripcion: {vacante.get('descripcion', '') if isinstance(vacante, dict) else ''}
Requisitos: {vacante.get('requisitos', '') if isinstance(vacante, dict) else ''}

HABILIDADES REQUERIDAS:
{json.dumps(habilidades_requeridas, ensure_ascii=False)}

CV:
{texto_anonimo[:12000]}
"""
    try:
        response = _post_json("/api/chat", {
            "model": _model(),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
        })
        data = json.loads(response["message"]["content"])
    except (OSError, URLError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return []

    allowed = {str(item).strip().lower(): str(item).strip() for item in habilidades_requeridas if str(item).strip()}
    detected = []
    for item in data.get("habilidades_detectadas", []):
        key = str(item).strip().lower()
        if key in allowed and allowed[key] not in detected:
            detected.append(allowed[key])
    return detected


def enriquecer_resultado(texto_cv, vacante, resultado):
    resultado["desglose"]["motor"] = "Reglas ponderadas"
    if not _enabled():
        return resultado

    schema = {
        "type": "object",
        "properties": {
            "habilidades_adicionales": {"type": "array", "items": {"type": "string"}},
            "justificacion": {"type": "string"},
            "accion_sugerida": {"type": "string"},
            "resumen_profesional": {"type": "string"},
            "fortalezas": {"type": "array", "items": {"type": "string"}},
            "brechas": {"type": "array", "items": {"type": "string"}},
            "preguntas_entrevista": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "habilidades_adicionales", "justificacion", "accion_sugerida", "resumen_profesional",
            "fortalezas", "brechas", "preguntas_entrevista",
        ],
    }
    texto_anonimo = anonimizar_texto_cv(texto_cv)
    prompt = f"""
Actúa como analista de selección. Evalúa el CV frente a la vacante sin inventar datos.
La puntuación determinística ya fue calculada y no debes modificarla.

VACANTE:
Título: {vacante.get('titulo', '')}
Descripción: {vacante.get('descripcion', '')}
Requisitos: {vacante.get('requisitos', '')}
Habilidades solicitadas: {vacante.get('habilidades', '')}

RESULTADO DETERMINÍSTICO:
Compatibilidad: {resultado['compatibilidad']}%
Estado: {resultado['estado']}
Habilidades encontradas: {resultado['habilidades_encontradas']}
Habilidades faltantes: {resultado['habilidades_faltantes']}

CV:
{texto_anonimo[:12000]}

Devuelve JSON según el esquema. Las habilidades adicionales deben aparecer realmente en el CV.
La justificación debe ser breve, profesional y basada en evidencia.
Genera también un resumen profesional breve, fortalezas verificables, brechas relevantes y entre 3 y 5 preguntas de entrevista personalizadas.
"""
    try:
        response = _post_json("/api/chat", {
            "model": _model(),
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
        })
        enrichment = json.loads(response["message"]["content"])
        additional = [str(item).strip() for item in enrichment["habilidades_adicionales"] if str(item).strip()]
        existing = {item.lower() for item in resultado["habilidades_encontradas"]}
        resultado["habilidades_encontradas"].extend(item for item in additional if item.lower() not in existing)
        resultado["justificacion"] = enrichment["justificacion"].strip() or resultado["justificacion"]
        resultado["accion_sugerida"] = enrichment["accion_sugerida"].strip() or resultado["accion_sugerida"]
        resultado["resumen_profesional"] = enrichment["resumen_profesional"].strip() or resultado["resumen_profesional"]
        resultado["fortalezas"] = [str(item).strip() for item in enrichment["fortalezas"] if str(item).strip()]
        resultado["brechas"] = [str(item).strip() for item in enrichment["brechas"] if str(item).strip()]
        resultado["preguntas_entrevista"] = [
            str(item).strip() for item in enrichment["preguntas_entrevista"] if str(item).strip()
        ]
        resultado["desglose"]["motor"] = f"Reglas ponderadas + Ollama ({_model()})"
    except (OSError, URLError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        resultado["desglose"]["motor"] = "Reglas ponderadas · Ollama no disponible"
        resultado["desglose"]["ollama_error"] = str(error)[:180]
    return resultado
