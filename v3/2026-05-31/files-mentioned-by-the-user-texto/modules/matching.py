import re
import unicodedata


AREA_ALIASES = {
    "tecnologia": {
        "sistemas", "informatica", "software", "computacion", "programacion", "ti", "tecnologia",
        "desarrollo", "datos", "redes",
    },
    "administracion": {
        "administracion", "contabilidad", "economia", "finanzas", "negocios", "gestion", "comercial",
        "recursos humanos",
    },
    "marketing": {"marketing", "comunicacion", "publicidad", "diseno", "ventas"},
    "operaciones": {"industrial", "operaciones", "logistica", "produccion", "calidad"},
    "construccion": {"civil", "arquitectura", "construccion", "obras"},
    "salud": {"medicina", "enfermeria", "salud", "psicologia", "farmacia"},
    "educacion": {"educacion", "docencia", "pedagogia"},
    "legal": {"derecho", "legal", "juridico"},
}


def normalizar(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def tokens_area(texto):
    clean = normalizar(texto)
    tokens = set(re.findall(r"[a-z0-9]+", clean))
    for area, aliases in AREA_ALIASES.items():
        if area in clean or any(alias in clean for alias in aliases):
            tokens.add(area)
    return tokens


def vacante_compatible_con_usuario(usuario, vacante):
    carrera = usuario.get("carrera") or ""
    if not carrera.strip():
        return True, "Completa tu carrera para personalizar mejor las vacantes."

    perfil = tokens_area(carrera)
    objetivo = vacante.get("carreras_objetivo") or vacante.get("area") or ""
    if not objetivo.strip():
        return True, "Vacante sin area objetivo definida."

    vacante_tokens = tokens_area(objetivo)
    matched = bool(perfil & vacante_tokens)
    reason = "Coincide con tu carrera o area profesional." if matched else "Pertenece a otra area."
    return matched, reason
