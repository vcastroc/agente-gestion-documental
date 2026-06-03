import re
from pathlib import Path

from docx import Document
from PyPDF2 import PdfReader


def extraer_texto_pdf(ruta_archivo):
    reader = PdfReader(str(ruta_archivo))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extraer_texto_docx(ruta_archivo):
    document = Document(str(ruta_archivo))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def extraer_texto(ruta_archivo):
    extension = Path(ruta_archivo).suffix.lower()
    if extension == ".pdf":
        return extraer_texto_pdf(ruta_archivo)
    if extension == ".docx":
        return extraer_texto_docx(ruta_archivo)
    raise ValueError("Formato no soportado. Use PDF o DOCX.")


def extraer_correo(texto):
    match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", texto)
    return match.group(0) if match else ""


def extraer_telefono(texto):
    match = re.search(r"(?:\+?\d[\s()-]*){7,15}", texto)
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


def extraer_nombre(texto):
    for line in texto.splitlines():
        clean = line.strip()
        if 2 <= len(clean.split()) <= 5 and not any(char.isdigit() for char in clean):
            return clean.title()
    return "Candidato sin nombre"
