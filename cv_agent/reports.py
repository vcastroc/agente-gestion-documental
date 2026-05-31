"""Action module: generates Excel and PDF reports in memory and on disk."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ranking import rank_candidates


def ranking_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "Posición": candidate["position"],
            "Nombre": candidate["name"],
            "Correo": candidate["email"],
            "Teléfono": candidate["phone"],
            "Experiencia (años)": candidate["experience_years"],
            "Compatibilidad (%)": candidate["score"],
            "Habilidades coincidentes": ", ".join(candidate["matched_skills"]),
            "Habilidades faltantes": ", ".join(candidate["missing_skills"]),
            "Seleccionado": "Sí" if candidate["selected"] else "No",
            "Estado": candidate["status"],
        }
        for candidate in rank_candidates(candidates)
    ]


def generate_excel(vacancy: dict[str, Any], candidates: list[dict[str, Any]]) -> bytes:
    output = BytesIO()
    ranking_df = pd.DataFrame(ranking_rows(candidates))
    vacancy_df = pd.DataFrame(
        [
            {
                "Cargo": vacancy["title"],
                "Área": vacancy["area"],
                "Experiencia requerida": vacancy["required_experience"],
                "Habilidades requeridas": ", ".join(vacancy["required_skills"]),
                "Fecha de creación": vacancy["created_at"],
            }
        ]
    )
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        ranking_df.to_excel(writer, sheet_name="Ranking", index=False)
        vacancy_df.to_excel(writer, sheet_name="Vacante", index=False)
        for sheet in writer.book.worksheets:
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
                cell.alignment = Alignment(horizontal="center")
            for column_cells in sheet.columns:
                length = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 45)
                sheet.column_dimensions[column_cells[0].column_letter].width = length
    return output.getvalue()


def generate_pdf(vacancy: dict[str, Any], candidates: list[dict[str, Any]]) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Reporte de Selección Inteligente de CVs", styles["Title"]),
        Spacer(1, 0.3 * cm),
        Paragraph(f"<b>Vacante:</b> {vacancy['title']} | <b>Área:</b> {vacancy['area']}", styles["BodyText"]),
        Paragraph(f"<b>Habilidades requeridas:</b> {', '.join(vacancy['required_skills'])}", styles["BodyText"]),
        Spacer(1, 0.4 * cm),
    ]
    data = [["Pos.", "Candidato", "Correo", "Compatibilidad", "Coincidencias", "Estado"]]
    for row in ranking_rows(candidates):
        data.append(
            [
                str(row["Posición"]),
                row["Nombre"],
                row["Correo"] or "Sin correo",
                f"{row['Compatibilidad (%)']:.2f}%",
                row["Habilidades coincidentes"] or "Ninguna",
                row["Estado"],
            ]
        )
    table = Table(data, colWidths=[1.2 * cm, 4.4 * cm, 5.5 * cm, 3 * cm, 8 * cm, 3.8 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2F8")]),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return output.getvalue()


def save_report(data: bytes, reports_dir: str | Path, filename: str) -> Path:
    path = Path(reports_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path
