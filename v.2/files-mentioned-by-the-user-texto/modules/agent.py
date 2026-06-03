"""Autonomous recruitment workflow triggered by application events."""
from pathlib import Path

from modules.analyzer import analizar_cv
from modules.database import (
    aprobar_borradores_correo,
    actualizar_candidato_extraido, actualizar_postulacion, crear_ejecucion_agente, crear_o_actualizar_candidato_usuario,
    eliminar_analisis_candidato_vacante, finalizar_ejecucion_agente, guardar_analisis,
    guardar_borrador_correo, guardar_evento_historial, obtener_candidatos, obtener_ranking,
    obtener_usuario_por_id, obtener_vacantes,
)
from modules.email_sender import generar_mensaje
from modules.reports import generar_excel, generar_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"


def _vacante(vacante_id):
    return next((item for item in obtener_vacantes() if item["id"] == vacante_id), None)


def preparar_acciones_vacante(vacante_id):
    vacante = _vacante(vacante_id)
    if not vacante:
        return []
    ranking = obtener_ranking(vacante["id"])
    for candidate in ranking:
        if candidate.get("decision_rrhh") != "Aprobado" or not candidate["correo"]:
            continue
        subject = f"Invitación a entrevista: {vacante['titulo']}"
        message = generar_mensaje(
            candidate["nombre"], vacante["titulo"], vacante["fecha_entrevista"], vacante["hora_entrevista"],
        )
        guardar_borrador_correo(candidate["candidato_id"], candidate["correo"], subject, message, vacante["id"])
    generar_excel(ranking, vacante)
    generar_pdf(ranking, vacante)
    encolados = aprobar_borradores_correo(vacante["id"])
    guardar_evento_historial("Reportes preparados", f"Vacante: {vacante['titulo']}")
    if encolados:
        guardar_evento_historial(
            "Correos automaticos en cola",
            f"{encolados} invitacion(es) aprobada(s) por RRHH listas para envio SMTP",
        )
    return ranking


def ejecutar_ciclo_masivo(vacante_id, candidatos_ids=None, origen="Carga masiva de CVs"):
    vacante = _vacante(vacante_id)
    execution_id = crear_ejecucion_agente(vacante_id, origen)
    if not vacante:
        finalizar_ejecucion_agente(execution_id, "Error", "No existe una vacante activa.")
        return {"estado": "Error", "procesados": 0, "detalle": "No existe una vacante activa."}
    candidates = obtener_candidatos()
    if candidatos_ids:
        candidates = [item for item in candidates if item["id"] in candidatos_ids]
    processed = 0
    errors = []
    try:
        for candidate in candidates:
            path = UPLOADS_DIR / (candidate["archivo"] or "")
            if not path.is_file() or path.suffix.lower() not in {".pdf", ".docx"}:
                continue
            try:
                result = analizar_cv(path, vacante)
                actualizar_candidato_extraido(candidate["id"], result)
                eliminar_analisis_candidato_vacante(candidate["id"], vacante_id)
                guardar_analisis(candidate["id"], vacante_id, result)
                processed += 1
            except Exception as error:
                errors.append(f"{path.name}: {error}")
                guardar_evento_historial("CV requiere revisión manual", f"{path.name}: {error}")
        ranking = preparar_acciones_vacante(vacante["id"])
        detail = f"{processed} CV(s) analizado(s), {len(ranking)} perfil(es) en ranking y acciones preparadas."
        if errors:
            detail += f" {len(errors)} CV(s) requieren revisión manual."
        finalizar_ejecucion_agente(execution_id, "Completado", detail)
        return {"estado": "Completado", "procesados": processed, "detalle": detail}
    except Exception as error:
        finalizar_ejecucion_agente(execution_id, "Error", str(error))
        return {"estado": "Error", "procesados": processed, "detalle": str(error)}


def ejecutar_ciclo_postulacion(usuario_id, vacante_id):
    vacante = _vacante(vacante_id)
    execution_id = crear_ejecucion_agente(vacante_id, "Postulación de candidato")
    user = obtener_usuario_por_id(usuario_id)
    if not user or not user.get("cv_archivo"):
        detail = "Postulación guardada. El candidato aún no cargó un CV para analizar."
        finalizar_ejecucion_agente(execution_id, "Pendiente", detail)
        return {"estado": "Pendiente", "detalle": detail}
    path = UPLOADS_DIR / user["cv_archivo"]
    if not vacante or not path.is_file():
        detail = "No se encontró la vacante o el archivo de CV."
        finalizar_ejecucion_agente(execution_id, "Error", detail)
        return {"estado": "Error", "detalle": detail}
    try:
        candidate_id = crear_o_actualizar_candidato_usuario(user)
        result = analizar_cv(path, vacante)
        actualizar_candidato_extraido(candidate_id, result)
        eliminar_analisis_candidato_vacante(candidate_id, vacante_id)
        guardar_analisis(candidate_id, vacante_id, result)
        actualizar_postulacion(usuario_id, vacante_id, result["compatibilidad"], result["estado"])
        preparar_acciones_vacante(vacante["id"])
        detail = f"CV analizado automáticamente: {result['compatibilidad']}% - {result['estado']}."
        finalizar_ejecucion_agente(execution_id, "Completado", detail)
        return {"estado": "Completado", "detalle": detail}
    except Exception as error:
        actualizar_postulacion(usuario_id, vacante_id, 0, "Revisión manual")
        finalizar_ejecucion_agente(execution_id, "Error", str(error))
        return {"estado": "Error", "detalle": str(error)}


def ejecutar_preanalisis_perfil(usuario_id):
    user = obtener_usuario_por_id(usuario_id)
    vacancies = obtener_vacantes(solo_activas=True)
    execution_id = crear_ejecucion_agente(None, "CV personal actualizado")
    if not user or not user.get("cv_archivo"):
        detail = "No existe un CV personal para analizar."
        finalizar_ejecucion_agente(execution_id, "Pendiente", detail)
        return {"estado": "Pendiente", "detalle": detail}
    path = UPLOADS_DIR / user["cv_archivo"]
    if not path.is_file():
        detail = "No se encontró el archivo del CV personal."
        finalizar_ejecucion_agente(execution_id, "Error", detail)
        return {"estado": "Error", "detalle": detail}
    candidate_id = crear_o_actualizar_candidato_usuario(user)
    processed = 0
    errors = []
    for vacancy in vacancies:
        try:
            result = analizar_cv(path, vacancy)
            actualizar_candidato_extraido(candidate_id, result)
            eliminar_analisis_candidato_vacante(candidate_id, vacancy["id"])
            guardar_analisis(candidate_id, vacancy["id"], result)
            processed += 1
        except Exception as error:
            errors.append(str(error))
    detail = f"Perfil comparado automáticamente con {processed} vacante(s) activa(s)."
    if errors:
        detail += f" {len(errors)} análisis requieren revisión manual."
    finalizar_ejecucion_agente(execution_id, "Completado" if processed else "Error", detail)
    return {"estado": "Completado" if processed else "Error", "detalle": detail}
