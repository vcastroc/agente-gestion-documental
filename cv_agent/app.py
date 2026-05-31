"""Streamlit UI for the autonomous CV analysis and selection agent."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from analyzer import CandidateAnalyzer
from database import Database
from email_sender import SMTPConfig, build_invitation, send_email
from extractor import CVExtractor
from ranking import rank_candidates, select_top_candidates
from reports import generate_excel, generate_pdf, save_report
from utils import safe_filename, split_items

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"
UPLOADS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="Agente Autónomo de CVs", page_icon="🤖", layout="wide")


@st.cache_resource
def get_services() -> tuple[Database, CVExtractor, CandidateAnalyzer]:
    return Database(), CVExtractor(), CandidateAnalyzer()


db, extractor, analyzer = get_services()


def initialize_state() -> None:
    defaults = {
        "current_vacancy_id": None,
        "current_process_id": None,
        "flash": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def current_vacancy() -> dict[str, Any] | None:
    vacancy_id = st.session_state.current_vacancy_id
    return db.get_vacancy(vacancy_id) if vacancy_id else None


def current_candidates() -> list[dict[str, Any]]:
    process_id = st.session_state.current_process_id
    return db.list_candidates(process_id) if process_id else []


def require_process() -> bool:
    if not st.session_state.current_process_id:
        st.info("Primero cree o seleccione una vacante y procese al menos un CV.")
        return False
    return True


def ranking_frame(candidates: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Posición": candidate["position"],
                "Nombre": candidate["name"],
                "Compatibilidad": f"{candidate['score']:.2f}%",
                "Coincidencias": ", ".join(candidate["matched_skills"]) or "Ninguna",
                "Faltantes": ", ".join(candidate["missing_skills"]) or "Ninguna",
                "Estado": candidate["status"],
            }
            for candidate in rank_candidates(candidates)
        ]
    )


def render_home() -> None:
    st.title("🤖 Agente Autónomo para Análisis y Selección Inteligente de CVs")
    st.caption("Sistema universitario de percepción, razonamiento, decisión, acción y retroalimentación.")
    candidates = current_candidates()
    selected = [candidate for candidate in candidates if candidate["selected"]]
    logs = db.list_email_logs(st.session_state.current_process_id) if st.session_state.current_process_id else []
    sent = len([log for log in logs if log["status"] in {"ENVIADO", "SIMULADO"}])
    columns = st.columns(4)
    columns[0].metric("Total candidatos", len(candidates))
    columns[1].metric("Compatibilidad promedio", f"{sum(c['score'] for c in candidates) / len(candidates):.2f}%" if candidates else "0%")
    columns[2].metric("Top candidato", rank_candidates(candidates)[0]["name"] if candidates else "Sin datos")
    columns[3].metric("Correos enviados", sent)
    st.subheader("Ciclo del agente autónomo")
    st.markdown(
        """
        1. **Percepción:** recibe la vacante y lee CVs PDF/DOCX.
        2. **Razonamiento:** extrae datos y calcula similitud TF-IDF, habilidades y experiencia.
        3. **Decisión:** ordena candidatos y preselecciona automáticamente el TOP 3.
        4. **Acción:** genera ranking, invitaciones y reportes.
        5. **Retroalimentación:** registra cada proceso y cada envío en SQLite.
        """
    )
    if selected:
        st.success(f"Preseleccionados actuales: {', '.join(candidate['name'] for candidate in selected)}")


def render_vacancy() -> None:
    st.header("📄 Gestión de Vacantes")
    with st.form("vacancy_form", clear_on_submit=True):
        title = st.text_input("Cargo", placeholder="Ej. Desarrollador Python Junior")
        area = st.text_input("Área", placeholder="Ej. Tecnología")
        description = st.text_area("Descripción", placeholder="Responsabilidades principales de la vacante")
        requirements = st.text_area("Requisitos", placeholder="Formación, conocimientos y condiciones")
        required_experience = st.number_input("Experiencia requerida (años)", min_value=0.0, step=0.5)
        skills = st.text_area("Habilidades requeridas", placeholder="Python, SQL, Git, Streamlit")
        submitted = st.form_submit_button("Guardar vacante", type="primary")
    if submitted:
        if not all([title.strip(), area.strip(), description.strip(), requirements.strip(), skills.strip()]):
            st.error("Complete todos los campos obligatorios.")
        else:
            vacancy_id = db.create_vacancy(
                {
                    "title": title.strip(),
                    "area": area.strip(),
                    "description": description.strip(),
                    "requirements": requirements.strip(),
                    "required_experience": required_experience,
                    "required_skills": split_items(skills),
                }
            )
            st.session_state.current_vacancy_id = vacancy_id
            st.session_state.current_process_id = None
            st.success("Vacante guardada y activada.")
    vacancies = db.list_vacancies()
    if vacancies:
        options = {f"#{item['id']} - {item['title']} ({item['area']})": item["id"] for item in vacancies}
        selected_label = st.selectbox("Vacante activa", list(options), index=0)
        if st.button("Activar vacante seleccionada"):
            st.session_state.current_vacancy_id = options[selected_label]
            st.session_state.current_process_id = None
            st.success("Vacante activa actualizada.")


def render_uploads() -> None:
    st.header("📂 Carga y Percepción de CVs")
    vacancy = current_vacancy()
    if not vacancy:
        st.warning("Cree o active una vacante antes de cargar CVs.")
        return
    st.info(f"Vacante activa: {vacancy['title']}")
    files = st.file_uploader("Suba múltiples CVs", type=["pdf", "docx"], accept_multiple_files=True)
    if st.button("Analizar CVs automáticamente", type="primary", disabled=not files):
        process_id = db.create_process(vacancy["id"])
        progress = st.progress(0)
        errors = []
        for index, uploaded in enumerate(files):
            filename = safe_filename(uploaded.name)
            destination = UPLOADS_DIR / f"process_{process_id}_{filename}"
            destination.write_bytes(uploaded.getbuffer())
            try:
                profile = extractor.extract(destination)
                analysis = analyzer.analyze(vacancy, profile)
                db.save_candidate(process_id, {"profile": profile, "analysis": analysis})
            except Exception as exc:
                errors.append(f"{uploaded.name}: {exc}")
            progress.progress((index + 1) / len(files))
        db.update_process_summary(process_id)
        candidates = db.list_candidates(process_id)
        ranked = select_top_candidates(candidates)
        db.update_selection(process_id, [candidate["id"] for candidate in ranked if candidate["selected"]])
        st.session_state.current_process_id = process_id
        if candidates:
            st.success(f"Proceso #{process_id}: {len(candidates)} CV(s) analizado(s). TOP 3 preseleccionado automáticamente.")
        if errors:
            st.warning("Algunos archivos no pudieron procesarse:\n\n" + "\n".join(errors))


def render_analysis() -> None:
    st.header("🤖 Análisis Inteligente")
    if not require_process():
        return
    candidates = current_candidates()
    for candidate in rank_candidates(candidates):
        with st.expander(f"#{candidate['position']} {candidate['name']} - {candidate['score']:.2f}%"):
            left, right = st.columns(2)
            left.write(f"**Correo:** {candidate['email'] or 'No identificado'}")
            left.write(f"**Teléfono:** {candidate['phone'] or 'No identificado'}")
            left.write(f"**Carrera:** {candidate['career']}")
            left.write(f"**Experiencia:** {candidate['experience_years']} años")
            right.write(f"**TF-IDF / similitud:** {candidate['similarity_score']:.2f}%")
            right.write(f"**Habilidades:** {candidate['skill_score']:.2f}%")
            right.write(f"**Experiencia:** {candidate['experience_score']:.2f}%")
            right.write(f"**Estado:** {candidate['status']}")
            st.write("**Habilidades coincidentes:**", ", ".join(candidate["matched_skills"]) or "Ninguna")
            st.write("**Habilidades faltantes:**", ", ".join(candidate["missing_skills"]) or "Ninguna")


def render_ranking() -> None:
    st.header("📊 Ranking y Selección Inteligente")
    if not require_process():
        return
    candidates = rank_candidates(current_candidates())
    st.dataframe(ranking_frame(candidates), use_container_width=True, hide_index=True)
    selected_default = [candidate["id"] for candidate in candidates if candidate["selected"]]
    labels = {candidate["id"]: f"#{candidate['position']} {candidate['name']} ({candidate['score']:.2f}%)" for candidate in candidates}
    selected_ids = st.multiselect(
        "Preseleccionados (editable manualmente)",
        options=list(labels),
        default=selected_default,
        format_func=lambda candidate_id: labels[candidate_id],
    )
    if st.button("Guardar selección"):
        db.update_selection(st.session_state.current_process_id, selected_ids)
        st.success("Selección actualizada.")


def render_email() -> None:
    st.header("📧 Correos Automáticos")
    if not require_process():
        return
    vacancy = current_vacancy()
    candidates = [candidate for candidate in current_candidates() if candidate["selected"]]
    if not candidates:
        st.warning("No hay candidatos preseleccionados.")
        return
    with st.expander("Configuración SMTP editable", expanded=True):
        simulation = st.toggle("Modo simulación (recomendado para la demostración)", value=True)
        sender = st.text_input("Correo Gmail remitente", placeholder="usuario@gmail.com")
        password = st.text_input("Contraseña de aplicación de Gmail", type="password")
        smtp_server = st.text_input("Servidor SMTP", value="smtp.gmail.com")
        smtp_port = st.number_input("Puerto SMTP", value=587, min_value=1, max_value=65535)
    left, right = st.columns(2)
    interview_date = left.date_input("Fecha de entrevista", value=date.today())
    interview_time = right.time_input("Hora de entrevista", value=time(9, 0))
    st.write(f"Se enviarán invitaciones a {len(candidates)} candidato(s).")
    if st.button("Enviar invitaciones", type="primary"):
        config = SMTPConfig(sender, password, smtp_server, int(smtp_port), simulation_mode=simulation)
        for candidate in candidates:
            subject, body = build_invitation(candidate["name"], vacancy["title"], str(interview_date), interview_time.strftime("%H:%M"))
            result = send_email(config, candidate["email"], subject, body)
            db.add_email_log(candidate["id"], candidate["email"], subject, body, result["status"], result["error"])
        st.success("Proceso de envío finalizado. Revise el registro inferior.")
    logs = db.list_email_logs(st.session_state.current_process_id)
    if logs:
        st.dataframe(pd.DataFrame(logs)[["candidate_name", "recipient", "status", "sent_at", "error_message"]], use_container_width=True, hide_index=True)


def render_reports() -> None:
    st.header("📥 Reportes PDF y Excel")
    if not require_process():
        return
    vacancy = current_vacancy()
    candidates = current_candidates()
    excel = generate_excel(vacancy, candidates)
    pdf = generate_pdf(vacancy, candidates)
    process_id = st.session_state.current_process_id
    save_report(excel, REPORTS_DIR, f"ranking_proceso_{process_id}.xlsx")
    save_report(pdf, REPORTS_DIR, f"reporte_proceso_{process_id}.pdf")
    left, right = st.columns(2)
    left.download_button("Descargar ranking Excel", excel, f"ranking_proceso_{process_id}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    right.download_button("Descargar reporte PDF", pdf, f"reporte_proceso_{process_id}.pdf", "application/pdf")
    st.success("Reportes generados y guardados localmente.")


def render_history() -> None:
    st.header("📚 Historial y Retroalimentación")
    processes = db.list_processes()
    if not processes:
        st.info("Todavía no existen procesos registrados.")
        return
    st.dataframe(pd.DataFrame(processes), use_container_width=True, hide_index=True)
    labels = {item["id"]: f"Proceso #{item['id']} - {item['vacancy_title']} - {item['created_at']}" for item in processes}
    process_id = st.selectbox("Ver detalle de proceso", list(labels), format_func=lambda item: labels[item])
    if st.button("Abrir proceso histórico"):
        process = next(item for item in processes if item["id"] == process_id)
        st.session_state.current_process_id = process_id
        st.session_state.current_vacancy_id = process["vacancy_id"]
        st.success("Proceso cargado como contexto activo.")
    details = db.list_candidates(process_id)
    if details:
        st.dataframe(ranking_frame(details), use_container_width=True, hide_index=True)


initialize_state()
st.sidebar.title("Menú principal")
pages = {
    "🏠 Inicio": render_home,
    "📄 Vacante": render_vacancy,
    "📂 CVs": render_uploads,
    "🤖 Análisis": render_analysis,
    "📊 Ranking": render_ranking,
    "📧 Correos": render_email,
    "📥 Reportes": render_reports,
    "📚 Historial": render_history,
}
page = st.sidebar.radio("Navegación", list(pages), label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"Modelo NLP: {extractor.model_name}")
st.sidebar.caption("Persistencia: SQLite")
pages[page]()
