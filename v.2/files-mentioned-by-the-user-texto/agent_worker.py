import argparse
import logging
import socket
import threading
import time
from pathlib import Path

from modules.agent import UPLOADS_DIR, ejecutar_ciclo_masivo, ejecutar_ciclo_postulacion, ejecutar_preanalisis_perfil
from modules.database import (
    actualizar_latido_worker,
    completar_evento_agente,
    encolar_evento_agente,
    fallar_evento_agente,
    guardar_alerta_agente,
    guardar_candidato,
    inicializar_bd,
    existe_hash_cv,
    obtener_archivos_cv_registrados,
    obtener_postulaciones_usuario,
    obtener_vacantes,
    reclamar_evento_agente,
    renovar_bloqueo_evento,
)
from modules.email_sender import enviar_correos_en_cola
from modules.file_utils import calcular_hash_archivo

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
WORKER_ID = f"{socket.gethostname()}-{id(object())}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "agent_worker.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("recruitai.worker")


def detectar_cvs_nuevos():
    registrados = obtener_archivos_cv_registrados()
    nuevos_ids = []
    for path in UPLOADS_DIR.glob("*"):
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx"} and path.name not in registrados:
            archivo_hash = calcular_hash_archivo(path)
            if existe_hash_cv(archivo_hash):
                logger.info("CV duplicado omitido: %s", path.name)
                continue
            nuevos_ids.append(guardar_candidato({
                "nombre": path.stem.replace("_", " ").title(), "archivo": path.name, "archivo_hash": archivo_hash,
            }))
    for vacancy in obtener_vacantes(solo_activas=True):
        if nuevos_ids:
            encolar_evento_agente("ANALIZAR_IMPORTADOS", {"vacante_id": vacancy["id"], "candidatos_ids": nuevos_ids})
    if nuevos_ids:
        logger.info("%s CV(s) nuevo(s) detectado(s) en uploads", len(nuevos_ids))
    return nuevos_ids


def _validar_resultado(result):
    if result.get("estado") == "Error":
        raise RuntimeError(result.get("detalle", "El agente no pudo completar el evento."))
    return result.get("detalle", "Evento completado")


def ejecutar_evento(event):
    payload = event["payload"]
    if event["tipo"] == "PREANALIZAR_PERFIL":
        detail = _validar_resultado(ejecutar_preanalisis_perfil(payload["usuario_id"]))
        for postulation in obtener_postulaciones_usuario(payload["usuario_id"]):
            encolar_evento_agente(
                "ANALIZAR_POSTULACION",
                {"usuario_id": payload["usuario_id"], "vacante_id": postulation["vacante_id"]},
            )
        return detail
    if event["tipo"] == "ANALIZAR_POSTULACION":
        return _validar_resultado(ejecutar_ciclo_postulacion(payload["usuario_id"], payload["vacante_id"]))
    if event["tipo"] == "ANALIZAR_IMPORTADOS":
        return _validar_resultado(
            ejecutar_ciclo_masivo(
                payload["vacante_id"],
                payload.get("candidatos_ids"),
                origen="Worker: importación externa",
            )
        )
    if event["tipo"] == "REPROCESAR_VACANTE":
        return _validar_resultado(
            ejecutar_ciclo_masivo(payload["vacante_id"], origen="Worker: reproceso solicitado")
        )
    if event["tipo"] == "ENVIAR_CORREOS":
        result = enviar_correos_en_cola(payload["vacante_id"])
        return f"{result['enviados']} correo(s) enviados por SMTP."
    raise ValueError(f"Tipo de evento no soportado: {event['tipo']}")


def _mantener_bloqueo(evento_id, worker_id, stop_event, interval_seconds=20):
    while not stop_event.wait(interval_seconds):
        if not renovar_bloqueo_evento(evento_id, worker_id):
            return
        actualizar_latido_worker(worker_id, "Procesando", f"Evento #{evento_id} en ejecucion")


def procesar_siguiente_evento(worker_id=WORKER_ID):
    event = reclamar_evento_agente(worker_id)
    if not event:
        return False
    actualizar_latido_worker(worker_id, "Procesando", f"Evento #{event['id']} - {event['tipo']}")
    stop_event = threading.Event()
    renewal = threading.Thread(
        target=_mantener_bloqueo, args=(event["id"], worker_id, stop_event), daemon=True,
    )
    renewal.start()
    try:
        detail = ejecutar_evento(event)
        completar_evento_agente(event["id"])
        logger.info("Evento #%s completado: %s", event["id"], detail)
    except Exception as error:
        state = fallar_evento_agente(event["id"], error)
        if state == "Error":
            guardar_alerta_agente(
                "Evento fallido", "El agente necesita atención",
                f"Evento #{event['id']} - {event['tipo']}: {str(error)[:300]}",
                "danger", f"evento-error:{event['id']}",
            )
        logger.exception("Evento #%s falló", event["id"])
    finally:
        stop_event.set()
        renewal.join(timeout=1)
    return True


def ejecutar_worker(poll_seconds=2, once=False):
    inicializar_bd()
    logger.info("Worker autónomo iniciado: %s", WORKER_ID)
    while True:
        actualizar_latido_worker(WORKER_ID)
        detectar_cvs_nuevos()
        processed = procesar_siguiente_evento()
        if once:
            break
        if not processed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker autónomo de RecruitAI")
    parser.add_argument("--poll-seconds", type=float, default=2, help="Intervalo de consulta de la cola")
    parser.add_argument("--once", action="store_true", help="Procesar como máximo un evento y salir")
    args = parser.parse_args()
    ejecutar_worker(args.poll_seconds, args.once)
