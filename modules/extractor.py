"""Extract text and profile hints from uploaded CV files."""

from __future__ import annotations

import re
from pathlib import Path

SKILLS = ["Python", "Flask", "SQL", "JavaScript", "React", "Figma", "UX Research", "Design Systems", "Machine Learning", "Excel", "Power BI", "Docker", "Git"]


def extract_text(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from PyPDF2 import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if path.suffix.lower() == ".docx":
        from docx import Document
        return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)
    if path.suffix.lower() == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    raise ValueError("Formato no soportado. Usa PDF, DOCX o TXT.")


def extract_profile(path: str | Path) -> dict:
    text = extract_text(path)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    phone = re.search(r"(?:\+?51[\s-]?)?9\d{8}", text)
    return {
        "name": lines[0] if lines else Path(path).stem.replace("_", " ").title(),
        "email": email.group(0) if email else "",
        "phone": phone.group(0) if phone else "",
        "skills": [skill for skill in SKILLS if skill.lower() in text.lower()],
        "raw_text": text,
    }
