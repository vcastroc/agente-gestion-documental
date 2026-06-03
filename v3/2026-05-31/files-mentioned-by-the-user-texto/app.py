from functools import wraps
import hmac
import os
import secrets
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from modules.database import (
    actualizar_estado_invitacion, actualizar_estado_vacante, actualizar_perfil_usuario, aprobar_borradores_correo,
    contar_alertas_agente, crear_usuario, existe_hash_cv, guardar_candidato, guardar_decision_rrhh,
    encolar_evento_agente, guardar_cv_usuario, guardar_evento_historial, guardar_postulacion, guardar_vacante, inicializar_bd,
    obtener_analisis_por_id, obtener_candidatos, obtener_correos, obtener_ejecuciones_agente, obtener_estado_worker, obtener_eventos_agente,
    marcar_alerta_agente_leida, marcar_alertas_agente_leidas, obtener_alertas_agente, obtener_historial,
    obtener_invitaciones_usuario, obtener_resumen_eventos_agente, reintentar_evento_agente,
    obtener_postulaciones_usuario, obtener_ranking, obtener_recomendaciones_usuario, obtener_usuario, obtener_usuario_por_id,
    obtener_vacante_por_id, obtener_vacantes,
)
from modules.agent import preparar_acciones_vacante
from modules.email_sender import smtp_configurado
from modules.file_utils import calcular_hash_archivo
from modules.matching import vacante_compatible_con_usuario
from modules.ollama_client import obtener_estado_ollama
from modules.recruitbot import responder_recruitbot
from modules.reports import generar_excel, generar_pdf

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"
ALLOWED_EXTENSIONS = {"pdf", "docx"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "demo-reclutamiento-inteligente-cambiar-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
UPLOADS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
inicializar_bd()


def role_required(role):
    """Allow each authenticated role to use only its own application area."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            if session.get("rol") != role:
                endpoint = "admin_dashboard" if session.get("rol") == "admin" else "candidate_dashboard"
                flash("No tienes permisos para acceder a esa sección.", "warning")
                return redirect(url_for(endpoint))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def _vacante_actual():
    vacantes = obtener_vacantes(solo_activas=True) or obtener_vacantes()
    return vacantes[0] if vacantes else None


def _vacante_seleccionada():
    vacante_id = session.get("vacante_id")
    return obtener_vacante_por_id(vacante_id) or _vacante_actual()


def _unique_upload_name(filename, prefix=""):
    safe_name = secure_filename(filename)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}{timestamp}_{safe_name}"


def _valid_upload(file):
    extension = file.filename.rsplit(".", 1)[-1].lower() if file and "." in file.filename else ""
    header = file.stream.read(4) if file else b""
    if file:
        file.stream.seek(0)
    return extension in ALLOWED_EXTENSIONS and (
        (extension == "pdf" and header == b"%PDF") or
        (extension == "docx" and header[:2] == b"PK")
    )


def _vacantes_por_area_usuario(usuario):
    compatibles, otras = [], []
    for vacancy in obtener_vacantes(solo_activas=True):
        matched, reason = vacante_compatible_con_usuario(usuario, vacancy)
        vacancy = dict(vacancy)
        vacancy["motivo_area"] = reason
        if matched:
            compatibles.append(vacancy)
        else:
            otras.append(vacancy)
    return compatibles, otras


@app.context_processor
def inject_csrf_token():
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(24)
        return session["_csrf_token"]
    context = {"csrf_token": csrf_token}
    if session.get("rol") == "admin":
        context["nav_vacantes"] = obtener_vacantes()
        context["nav_vacante"] = _vacante_seleccionada()
    return context


@app.before_request
def csrf_protect():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        payload = request.get_json(silent=True) or {}
        received = request.form.get("_csrf_token", "") or request.headers.get("X-CSRFToken", "") or payload.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(expected, received):
            flash("La solicitud expiró o no es válida. Inténtalo nuevamente.", "warning")
            if request.is_json:
                return jsonify({"error": "csrf", "message": "Solicitud expirada o no valida."}), 400
            return redirect(request.referrer or url_for("landing"))


@app.route("/chatbot", methods=["POST"])
def chatbot():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    history = session.get("recruitbot_history", [])
    answer = responder_recruitbot(
        message,
        history=history,
        role=session.get("rol"),
        user_id=session.get("usuario_id"),
    )
    session["recruitbot_history"] = (
        history + [{"role": "user", "content": message}, {"role": "assistant", "content": answer}]
    )[-12:]
    return jsonify({"answer": answer})


@app.route("/")
def landing():
    ranking_data = obtener_ranking()
    return render_template(
        "landing.html", vacantes=obtener_vacantes(solo_activas=True)[:3],
        stats={"vacantes": len(obtener_vacantes(solo_activas=True)), "candidatos": len(obtener_candidatos()), "analizados": len(ranking_data)},
    )


@app.route("/sobre-nosotros")
def sobre_nosotros():
    return render_template("sobre.html")


@app.route("/vacantes-publicas")
def vacantes_publicas():
    return render_template("vacantes_publicas.html", vacantes=obtener_vacantes(solo_activas=True))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = obtener_usuario(request.form["correo"].strip().lower())
        if user and check_password_hash(user["password"], request.form["password"]):
            session["usuario"] = user["nombre"]
            session["usuario_id"] = user["id"]
            session["rol"] = user["rol"]
            endpoint = "admin_dashboard" if user["rol"] == "admin" else "candidate_dashboard"
            return redirect(url_for(endpoint))
        flash("Correo o contraseña incorrectos.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
@app.route("/registro", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if request.form["password"] != request.form["confirmar_password"]:
            flash("Las contraseñas no coinciden.", "warning")
            return render_template("register.html")
        try:
            crear_usuario(
                request.form["nombre"], request.form["correo"].strip().lower(), request.form["password"],
                "candidato", request.form["telefono"], request.form["universidad"],
                request.form["carrera"], request.form["ciudad"],
            )
            flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("login"))
        except Exception:
            flash("No fue posible registrar la cuenta. Verifica si el correo ya existe.", "danger")
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    endpoint = "admin_dashboard" if session["rol"] == "admin" else "candidate_dashboard"
    return redirect(url_for(endpoint))


@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    vacancy = _vacante_seleccionada()
    candidates, vacancies, ranking, emails = obtener_candidatos(), obtener_vacantes(), obtener_ranking(vacancy["id"]), obtener_correos(vacancy["id"])
    metrics = {
        "candidatos": len(candidates), "vacantes": len(vacancies), "analizados": len(ranking),
        "correos": len(emails), "mejor": ranking[0]["compatibilidad"] if ranking else 0,
    }
    return render_template(
        "dashboard_admin.html", metrics=metrics, historial=obtener_historial(6),
        ejecuciones=obtener_ejecuciones_agente(5), eventos_agente=obtener_eventos_agente(6),
        resumen_eventos=obtener_resumen_eventos_agente(), estado_worker=obtener_estado_worker(),
        estado_ollama=obtener_estado_ollama(),
        alertas_agente=obtener_alertas_agente(4, solo_no_leidas=True),
        vacantes=vacancies, vacante=vacancy,
    )


@app.route("/admin/agente")
@role_required("admin")
def control_agente():
    return render_template(
        "control_agente.html", estado_worker=obtener_estado_worker(), estado_ollama=obtener_estado_ollama(),
        resumen_eventos=obtener_resumen_eventos_agente(), eventos=obtener_eventos_agente(50),
        alertas=obtener_alertas_agente(30), alertas_pendientes=contar_alertas_agente(),
    )


@app.route("/admin/agente/eventos/<int:evento_id>/reintentar", methods=["POST"])
@role_required("admin")
def reintentar_evento(evento_id):
    if reintentar_evento_agente(evento_id):
        flash(f"Evento #{evento_id} reenviado a la cola.", "success")
    else:
        flash("Solo pueden reintentarse eventos que terminaron con error.", "warning")
    return redirect(url_for("control_agente"))


@app.route("/admin/agente/alertas/<int:alerta_id>/leer", methods=["POST"])
@role_required("admin")
def leer_alerta(alerta_id):
    marcar_alerta_agente_leida(alerta_id)
    return redirect(url_for("control_agente"))


@app.route("/admin/agente/alertas/leer-todas", methods=["POST"])
@role_required("admin")
def leer_alertas():
    marcar_alertas_agente_leidas()
    flash("Alertas marcadas como revisadas.", "success")
    return redirect(url_for("control_agente"))


@app.route("/admin/vacantes", methods=["GET", "POST"])
@app.route("/vacantes", methods=["GET", "POST"])
@role_required("admin")
def vacantes():
    if request.method == "POST":
        total_weight = sum(int(request.form.get(name, 0) or 0) for name in ("peso_habilidades", "peso_experiencia", "peso_estudios"))
        observation = int(request.form.get("umbral_observacion", 60) or 60)
        preselection = int(request.form.get("umbral_preseleccion", 80) or 80)
        if total_weight <= 0 or observation >= preselection:
            flash("Revisa la configuración del agente: los pesos deben sumar más de 0 y el umbral de observación debe ser menor.", "warning")
            return redirect(url_for("vacantes"))
        guardar_vacante(request.form.to_dict())
        flash("Vacante registrada correctamente.", "success")
        return redirect(url_for("vacantes"))
    return render_template("vacantes.html", vacantes=obtener_vacantes())


@app.route("/admin/candidatos")
@app.route("/candidatos")
@role_required("admin")
def candidatos():
    return render_template("candidatos.html", candidatos=obtener_candidatos())


@app.route("/admin/carga-cvs", methods=["GET", "POST"])
@app.route("/carga-cvs", methods=["GET", "POST"])
@role_required("admin")
def carga_cvs():
    uploaded_ids = []
    duplicated = 0
    if request.method == "POST":
        for file in request.files.getlist("cvs"):
            if not file.filename or not _valid_upload(file):
                continue
            filename = _unique_upload_name(file.filename, "masivo_")
            path = UPLOADS_DIR / filename
            file.save(path)
            archivo_hash = calcular_hash_archivo(path)
            if existe_hash_cv(archivo_hash):
                path.unlink(missing_ok=True)
                duplicated += 1
                continue
            candidate_id = guardar_candidato({
                "nombre": Path(filename).stem.replace("_", " ").title(),
                "archivo": filename, "archivo_hash": archivo_hash,
            })
            uploaded_ids.append(candidate_id)
        if uploaded_ids:
            encolar_evento_agente(
                "ANALIZAR_IMPORTADOS",
                {"vacante_id": _vacante_seleccionada()["id"], "candidatos_ids": uploaded_ids},
            )
            flash(f"{len(uploaded_ids)} CV(s) cargado(s). El worker los analizará en segundo plano.", "success")
        else:
            flash("No se encontraron archivos PDF o DOCX válidos.", "warning")
        if duplicated:
            flash(f"{duplicated} CV(s) duplicado(s) fueron omitidos.", "info")
        return redirect(url_for("carga_cvs"))
    return render_template("carga_cvs.html", candidatos=obtener_candidatos())


@app.route("/admin/analisis", methods=["GET", "POST"])
@app.route("/analisis", methods=["GET", "POST"])
@app.route("/analizar", methods=["GET", "POST"])
@role_required("admin")
def analisis():
    if request.method == "POST":
        vacante = _vacante_seleccionada()
        encolar_evento_agente("REPROCESAR_VACANTE", {"vacante_id": vacante["id"]})
        flash("Reproceso solicitado. El worker autónomo lo ejecutará en segundo plano.", "success")
        return redirect(url_for("ranking"))
    return render_template("analisis.html", vacante=_vacante_seleccionada(), candidatos=obtener_candidatos())


@app.route("/admin/ranking")
@app.route("/ranking")
@role_required("admin")
def ranking():
    vacancy = _vacante_seleccionada()
    return render_template("ranking.html", ranking=obtener_ranking(vacancy["id"]), vacante=vacancy)


@app.route("/admin/ficha-candidato/<int:analisis_id>")
@role_required("admin")
def ficha_candidato(analisis_id):
    analysis = obtener_analisis_por_id(analisis_id)
    if not analysis:
        flash("No se encontró la ficha solicitada.", "warning")
        return redirect(url_for("ranking"))
    return render_template("ficha_candidato.html", candidato=analysis)


@app.route("/admin/decision")
@app.route("/decision")
@role_required("admin")
def decision():
    ranking_data = obtener_ranking(_vacante_seleccionada()["id"])
    return render_template("decision.html", recomendado=ranking_data[0] if ranking_data else None, ranking=ranking_data)


@app.route("/admin/decision/<int:analisis_id>/<estado>", methods=["POST"])
@role_required("admin")
def resolver_candidato(analisis_id, estado):
    analysis = obtener_analisis_por_id(analisis_id)
    if not analysis or estado not in {"Aprobado", "Rechazado", "Pendiente"}:
        flash("No fue posible registrar la decision.", "warning")
    else:
        guardar_decision_rrhh(
            analysis["candidato_id"], analysis["vacante_id"], estado, request.form.get("comentario", ""),
        )
        preparar_acciones_vacante(analysis["vacante_id"])
        if estado == "Aprobado":
            flash("Decision registrada. La invitacion se envio automaticamente a la cola SMTP.", "success")
        else:
            flash(f"Decision de RRHH registrada: {estado}.", "success")
    return redirect(request.referrer or url_for("decision"))


@app.route("/admin/correos", methods=["GET", "POST"])
@app.route("/correos", methods=["GET", "POST"])
@role_required("admin")
def correos():
    if request.method == "POST":
        total = aprobar_borradores_correo(_vacante_seleccionada()["id"])
        if total:
            flash(f"{total} correo(s) aprobado(s). El worker realizara el envio SMTP en segundo plano.", "success")
        else:
            flash("No hay borradores pendientes de aprobacion.", "info")
        return redirect(url_for("correos"))
    vacancy = _vacante_seleccionada()
    return render_template(
        "correos.html", ranking=obtener_ranking(vacancy["id"]),
        correos=obtener_correos(vacancy["id"]), smtp_configurado=smtp_configurado(),
    )


@app.route("/admin/reportes", methods=["GET", "POST"])
@app.route("/reportes", methods=["GET", "POST"])
@role_required("admin")
def reportes():
    vacancy = _vacante_seleccionada()
    ranking_data = obtener_ranking(vacancy["id"])
    if request.method == "POST":
        report_type = request.form["tipo"]
        path = generar_excel(ranking_data, vacancy) if report_type == "excel" else generar_pdf(ranking_data, vacancy)
        guardar_evento_historial("Reporte generado", path.name)
        return redirect(url_for("descargar_reporte", filename=path.name))
    summary = {
        "total": len(ranking_data),
        "promedio": round(sum(item["compatibilidad"] for item in ranking_data) / len(ranking_data), 2) if ranking_data else 0,
        "preseleccionados": sum(item["estado"] == "Preseleccionado" for item in ranking_data),
        "no_recomendados": sum(item["estado"] == "No recomendado" for item in ranking_data),
    }
    return render_template("reportes.html", resumen=summary, vacante=vacancy, recomendado=ranking_data[0] if ranking_data else None)


@app.route("/reportes/descargar/<path:filename>")
@role_required("admin")
def descargar_reporte(filename):
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/admin/historial")
@app.route("/historial")
@role_required("admin")
def historial():
    return render_template("historial.html", historial=obtener_historial())


def _current_candidate():
    return obtener_usuario_por_id(session["usuario_id"])


@app.route("/candidato/dashboard")
@role_required("candidato")
def candidate_dashboard():
    user = _current_candidate()
    postulations = obtener_postulaciones_usuario(user["id"])
    invitations = obtener_invitaciones_usuario(user["correo"])
    vacantes_area, otras_vacantes = _vacantes_por_area_usuario(user)
    return render_template(
        "dashboard_candidato.html", usuario=user, postulaciones=postulations, invitaciones=invitations,
        vacantes=vacantes_area, otras_vacantes=otras_vacantes, recomendaciones=obtener_recomendaciones_usuario(user["id"]),
    )


@app.route("/candidato/perfil", methods=["GET", "POST"])
@role_required("candidato")
def perfil_candidato():
    if request.method == "POST":
        actualizar_perfil_usuario(session["usuario_id"], request.form.to_dict())
        session["usuario"] = request.form["nombre"]
        flash("Perfil actualizado correctamente.", "success")
        return redirect(url_for("perfil_candidato"))
    return render_template("perfil_candidato.html", usuario=_current_candidate())


@app.route("/candidato/mi-cv", methods=["GET", "POST"])
@role_required("candidato")
def mi_cv():
    if request.method == "POST":
        file = request.files.get("cv")
        if not file or not _valid_upload(file):
            flash("Selecciona un archivo PDF o DOCX válido.", "warning")
        else:
            filename = _unique_upload_name(file.filename, f"usuario_{session['usuario_id']}_")
            path = UPLOADS_DIR / filename
            file.save(path)
            archivo_hash = calcular_hash_archivo(path)
            if existe_hash_cv(archivo_hash):
                path.unlink(missing_ok=True)
                flash("Ese CV ya se encuentra registrado. No fue necesario volver a procesarlo.", "info")
                return redirect(url_for("mi_cv"))
            guardar_cv_usuario(session["usuario_id"], filename, archivo_hash)
            postulations = obtener_postulaciones_usuario(session["usuario_id"])
            if postulations:
                flash("Tu CV fue actualizado. El worker procesará tus postulaciones automáticamente.", "success")
            else:
                flash("Tu CV fue guardado. El worker buscará oportunidades recomendadas automáticamente.", "success")
        return redirect(url_for("mi_cv"))
    return render_template("mi_cv.html", usuario=_current_candidate())


@app.route("/candidato/vacantes")
@role_required("candidato")
def vacantes_disponibles():
    user = _current_candidate()
    vacantes_area, otras_vacantes = _vacantes_por_area_usuario(user)
    return render_template(
        "vacantes_disponibles.html", usuario=user, vacantes=vacantes_area, otras_vacantes=otras_vacantes,
    )


@app.route("/candidato/postular/<int:vacante_id>", methods=["POST"])
@role_required("candidato")
def postular_vacante(vacante_id):
    vacancy = obtener_vacante_por_id(vacante_id)
    if not vacancy or vacancy["estado"] != "Activa":
        flash("La vacante seleccionada no existe.", "warning")
    elif guardar_postulacion(session["usuario_id"], vacante_id):
        flash("Postulación registrada. El worker autónomo iniciará el análisis.", "success")
    else:
        flash("Ya te postulaste a esta vacante.", "info")
    return redirect(url_for("mis_postulaciones"))


@app.route("/admin/vacante-activa/<int:vacante_id>", methods=["POST"])
@role_required("admin")
def seleccionar_vacante(vacante_id):
    if obtener_vacante_por_id(vacante_id):
        session["vacante_id"] = vacante_id
        flash("Vacante activa actualizada.", "success")
    else:
        flash("La vacante seleccionada no existe.", "warning")
    return redirect(request.referrer or url_for("admin_dashboard"))


@app.route("/admin/vacantes/<int:vacante_id>/estado/<estado>", methods=["POST"])
@role_required("admin")
def cambiar_estado_vacante(vacante_id, estado):
    if actualizar_estado_vacante(vacante_id, estado):
        guardar_evento_historial("Estado de vacante actualizado", f"Vacante #{vacante_id}: {estado}")
        flash(f"Vacante marcada como {estado}.", "success")
    else:
        flash("No fue posible actualizar la vacante.", "warning")
    return redirect(url_for("vacantes"))


@app.route("/candidato/postulaciones")
@role_required("candidato")
def mis_postulaciones():
    return render_template("mis_postulaciones.html", postulaciones=obtener_postulaciones_usuario(session["usuario_id"]))


@app.route("/candidato/invitaciones")
@role_required("candidato")
def invitaciones():
    user = _current_candidate()
    return render_template("invitaciones.html", invitaciones=obtener_invitaciones_usuario(user["correo"]))


@app.route("/candidato/invitaciones/<int:correo_id>/<estado>", methods=["POST"])
@role_required("candidato")
def responder_invitacion(correo_id, estado):
    user = _current_candidate()
    if actualizar_estado_invitacion(user["correo"], correo_id, estado):
        flash("Respuesta registrada correctamente.", "success")
    else:
        flash("No fue posible actualizar la invitación.", "warning")
    return redirect(url_for("invitaciones"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
