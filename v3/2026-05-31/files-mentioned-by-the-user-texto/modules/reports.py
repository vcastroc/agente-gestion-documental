from pathlib import Path

import pandas as pd
from fpdf import FPDF

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def _report_name(vacante, extension):
    title = "".join(char if char.isalnum() else "_" for char in vacante.get("titulo", "vacante")).strip("_")
    return f"ranking_{vacante['id']}_{title}.{extension}"


def generar_excel(ranking, vacante=None):
    REPORTS_DIR.mkdir(exist_ok=True)
    vacante = vacante or {"id": "general", "titulo": "candidatos"}
    path = REPORTS_DIR / _report_name(vacante, "xlsx")
    rows = [{
        "Candidato": item["nombre"],
        "Correo": item.get("correo", ""),
        "Compatibilidad": item["compatibilidad"],
        "Estado": item["estado"],
        "Habilidades": item.get("habilidades_encontradas", ""),
        "Justificación": item.get("justificacion", ""),
        "Acción sugerida": item.get("accion_sugerida", ""),
        "Resumen profesional": item.get("resumen_profesional", ""),
        "Fortalezas": ", ".join(item.get("fortalezas", [])),
        "Brechas": ", ".join(item.get("brechas", [])),
        "Preguntas de entrevista": " | ".join(item.get("preguntas_entrevista", [])),
    } for item in ranking]
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def generar_pdf(ranking, vacante):
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / _report_name(vacante, "pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Reporte de reclutamiento inteligente", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Vacante: {vacante.get('titulo', 'Sin vacante')}", ln=True)
    pdf.ln(3)
    for index, item in enumerate(ranking, 1):
        line = f"{index}. {item['nombre']} - {item['compatibilidad']}% - {item['estado']}"
        pdf.multi_cell(0, 7, line.encode("latin-1", "replace").decode("latin-1"))
    pdf.output(str(path))
    return path
