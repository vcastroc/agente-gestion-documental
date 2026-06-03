import re
import unicodedata

from modules.extractor import extraer_correo, extraer_nombre, extraer_telefono, extraer_texto
from modules.ollama_client import enriquecer_resultado
from modules.ranking import asignar_estado

HABILIDADES = [
    "Python", "Java", "SQL", "Git", "Excel", "Power BI", "HTML", "CSS",
    "JavaScript", "Flask", "Django", "Machine Learning", "Scrum", "Linux",
    "MySQL", "PostgreSQL", "React", "Node.js", "Comunicación", "Trabajo en equipo",
]


def limpiar_texto(texto):
    normalized = unicodedata.normalize("NFD", texto.lower())
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip()


def extraer_habilidades(texto):
    clean = limpiar_texto(texto)
    found = []
    for skill in HABILIDADES:
        normalized = limpiar_texto(skill)
        pattern = rf"(?<![\w]){re.escape(normalized)}(?![\w])"
        if re.search(pattern, clean):
            found.append(skill)
    return found


def _skills_vacante(vacante):
    if isinstance(vacante, dict):
        source = vacante.get("habilidades", "") or vacante.get("requisitos", "")
    else:
        source = vacante
    requested = [item.strip() for item in re.split(r"[,;\n]", source) if item.strip()]
    return requested or extraer_habilidades(source)


def habilidades_faltantes(skills_cv, skills_vacante):
    found = {limpiar_texto(item) for item in skills_cv}
    return [item for item in skills_vacante if limpiar_texto(item) not in found]


def extraer_experiencia(texto):
    clean = limpiar_texto(texto)
    years = [int(value) for value in re.findall(r"(\d{1,2})\s*(?:anos?|years?)", clean)]
    return max(years, default=0)


def detectar_estudios(texto):
    clean = limpiar_texto(texto)
    levels = [
        ("Posgrado", ("maestria", "master", "posgrado", "doctorado")),
        ("Universitario", ("universidad", "universitario", "ingenieria", "licenciatura", "bachiller")),
        ("Técnico", ("tecnico", "instituto")),
        ("Secundaria", ("secundaria",)),
    ]
    for level, aliases in levels:
        if any(alias in clean for alias in aliases):
            return level
    return "No identificado"


def _score_studies(found, required):
    if not required:
        return 100.0
    levels = {"No identificado": 0, "Secundaria": 1, "Técnico": 2, "Universitario": 3, "Posgrado": 4}
    return 100.0 if levels.get(found, 0) >= levels.get(required, 0) else 0.0


def _weights(vacante):
    weights = {
        "habilidades": float(vacante.get("peso_habilidades", 70) or 0),
        "experiencia": float(vacante.get("peso_experiencia", 20) or 0),
        "estudios": float(vacante.get("peso_estudios", 10) or 0),
    }
    total = sum(weights.values()) or 100
    return {key: value / total for key, value in weights.items()}


def calcular_compatibilidad(cv_texto, vacante):
    required = _skills_vacante(vacante)
    cv_skills = extraer_habilidades(cv_texto)
    missing = habilidades_faltantes(cv_skills, required)
    skill_score = ((len(required) - len(missing)) / len(required) * 100) if required else 100.0
    required_experience = int(vacante.get("experiencia", 0) or 0)
    found_experience = extraer_experiencia(cv_texto)
    experience_score = min(found_experience / required_experience * 100, 100) if required_experience else 100.0
    studies_score = _score_studies(detectar_estudios(cv_texto), vacante.get("estudios"))
    weights = _weights(vacante)
    return round(
        skill_score * weights["habilidades"] +
        experience_score * weights["experiencia"] +
        studies_score * weights["estudios"],
        2,
    )


def analizar_cv(ruta_archivo, vacante):
    texto = extraer_texto(ruta_archivo)
    if len(texto.strip()) < 20:
        raise ValueError("El CV no contiene texto suficiente. Si es un PDF escaneado, requiere OCR.")
    skills = extraer_habilidades(texto)
    required = _skills_vacante(vacante)
    compatibility = calcular_compatibilidad(texto, vacante)
    missing = habilidades_faltantes(skills, required)
    experience = extraer_experiencia(texto)
    studies = detectar_estudios(texto)
    required_experience = int(vacante.get("experiencia", 0) or 0)
    state = asignar_estado(
        compatibility,
        int(vacante.get("umbral_preseleccion", 80) or 80),
        int(vacante.get("umbral_observacion", 60) or 60),
    )
    breakdown = {
        "habilidades": f"{len(required) - len(missing)} de {len(required)} requeridas",
        "experiencia": f"{experience} de {required_experience} años requeridos",
        "estudios": f"{studies} / requerido: {vacante.get('estudios') or 'No especificado'}",
    }
    justification = (
        f"Coincide con {breakdown['habilidades']}. "
        f"Experiencia detectada: {experience} año(s). Estudios detectados: {studies}. "
        f"Habilidades faltantes: {', '.join(missing) if missing else 'ninguna'}."
    )
    action = {
        "Preseleccionado": "Preparar invitación a entrevista para aprobación de RRHH.",
        "En observación": "Solicitar revisión manual de RRHH antes de continuar.",
        "No recomendado": "Conservar en historial sin preparar contacto automático.",
    }[state]
    strengths = skills[:5] or ["Perfil disponible para revisión manual"]
    gaps = missing[:5] or ["No se detectaron brechas técnicas explícitas"]
    questions = [
        f"Describe un proyecto donde aplicaste {skills[0]}." if skills else "Describe tu proyecto profesional más relevante.",
        f"¿Cómo abordarías el aprendizaje de {missing[0]}?" if missing else "¿Cuál fue el reto técnico más exigente que resolviste?",
        "¿Qué responsabilidades asumiste en tu experiencia más reciente?",
    ]
    result = {
        "nombre": extraer_nombre(texto),
        "correo": extraer_correo(texto),
        "telefono": extraer_telefono(texto),
        "texto": texto,
        "habilidades_encontradas": skills,
        "habilidades_faltantes": missing,
        "compatibilidad": compatibility,
        "estado": state,
        "experiencia_detectada": experience,
        "estudios_detectados": studies,
        "desglose": breakdown,
        "justificacion": justification,
        "accion_sugerida": action,
        "resumen_profesional": (
            f"Perfil con {experience} año(s) de experiencia detectada y nivel de estudios {studies}. "
            f"Compatibilidad calculada: {compatibility}% para la vacante {vacante.get('titulo', '')}."
        ),
        "fortalezas": strengths,
        "brechas": gaps,
        "preguntas_entrevista": questions,
    }
    return enriquecer_resultado(texto, vacante, result)
