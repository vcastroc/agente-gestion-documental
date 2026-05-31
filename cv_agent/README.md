# Agente Autónomo para Análisis y Selección Inteligente de CVs

Aplicación universitaria en Python y Streamlit que recibe una vacante, procesa múltiples CVs PDF/DOCX, calcula compatibilidad con NLP y Machine Learning, preselecciona el TOP 3, genera invitaciones, exporta reportes y conserva historial en SQLite.

## Arquitectura del agente

| Etapa | Implementación |
| --- | --- |
| Percepción | `extractor.py` lee CVs con PyMuPDF y python-docx; `app.py` recibe vacantes |
| Razonamiento | `analyzer.py` compara TF-IDF, similitud coseno, habilidades y experiencia |
| Toma de decisiones | `ranking.py` ordena y preselecciona automáticamente el TOP 3 |
| Acción | `email_sender.py` envía invitaciones; `reports.py` genera PDF y Excel |
| Retroalimentación | `database.py` registra procesos, candidatos y envíos en SQLite |

La compatibilidad se calcula así:

```text
45% similitud TF-IDF + 40% habilidades requeridas + 15% experiencia
```

## Estructura

```text
cv_agent/
├── app.py
├── database.py
├── extractor.py
├── analyzer.py
├── ranking.py
├── email_sender.py
├── reports.py
├── utils.py
├── requirements.txt
├── README.md
├── data/
├── reports/
├── uploads/
├── models/
├── database/
└── tests/
```

## Instalación

Desde esta carpeta:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download es_core_news_sm
streamlit run app.py
```

El modelo `es_core_news_sm` mejora la detección de nombres. La aplicación también funciona sin descargarlo mediante un modelo base de spaCy y reglas determinísticas.

## Demostración rápida

Genere tres CVs DOCX de prueba:

```powershell
python tests\generate_demo_cvs.py
```

En la interfaz:

1. Cree una vacante de `Desarrollador Python`.
2. Use habilidades `Python, SQL, Git, Streamlit, Scikit-Learn`.
3. Abra `CVs` y cargue los archivos generados en `data\demo_cvs`.
4. Revise `Análisis`, `Ranking`, `Correos`, `Reportes` e `Historial`.
5. Mantenga activado el modo simulación de correo durante la exposición.

Para enviar correos reales con Gmail, use una contraseña de aplicación de Google, no la contraseña normal de la cuenta.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Esquema SQLite

La base se crea automáticamente en `database\cv_agent.db`.
El archivo ejecutable del esquema también está disponible en `database\schema.sql`.

```sql
vacancies(id, title, area, description, requirements,
          required_experience, required_skills, created_at)
processes(id, vacancy_id, created_at, status,
          total_candidates, average_score)
candidates(id, process_id, file_name, name, email, phone, career,
           experience_years, skills, languages, certifications, projects,
           raw_text, score, similarity_score, skill_score, experience_score,
           matched_skills, missing_skills, status, selected, created_at)
email_logs(id, candidate_id, recipient, subject, body,
           status, error_message, sent_at)
```

Los campos de listas se almacenan como JSON válido dentro de SQLite.
