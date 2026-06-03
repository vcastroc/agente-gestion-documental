# RecruitAI - Agente Autonomo de Reclutamiento Inteligente

RecruitAI es una aplicacion web desarrollada con Flask, SQLite, Ollama y SMTP para automatizar y asistir procesos de seleccion de personal.

El sistema permite gestionar vacantes, candidatos, CVs, analisis de compatibilidad, rankings, decisiones de RRHH, invitaciones por correo, reportes e historial. Ademas incluye un worker autonomo que procesa eventos en segundo plano y un chatbot flotante llamado RecruitBot.

## Caracteristicas principales

- Portal publico con informacion del sistema y vacantes disponibles.
- Login y registro de usuarios.
- Separacion de roles entre administrador/RRHH y candidato.
- Dashboard administrativo para RRHH.
- Dashboard del candidato.
- Creacion y gestion de vacantes.
- Vacantes agrupadas por area/carrera del candidato.
- Carga individual de CV por candidato.
- Carga masiva de CVs por RRHH.
- Extraccion de texto desde PDF y DOCX.
- Analisis automatico de habilidades, experiencia y estudios.
- Deteccion flexible de habilidades segun lo solicitado en cada vacante.
- Apoyo semantico opcional con Ollama para reconocer equivalencias profesionales.
- Ranking explicable de candidatos.
- Ficha inteligente del candidato con fortalezas, brechas y preguntas de entrevista.
- Decision final de RRHH separada de la recomendacion de IA.
- Envio real de correos por SMTP.
- Reportes en PDF y Excel.
- Historial del sistema.
- Centro de control del agente autonomo.
- RecruitBot, asistente IA flotante integrado en toda la aplicacion.
- Pruebas automatizadas con `unittest`.

## Tecnologias utilizadas

- Python
- Flask
- SQLite
- Bootstrap
- JavaScript
- Ollama local
- SMTP
- PyPDF
- python-docx
- openpyxl
- reportlab

## Estructura del proyecto

```text
app.py                  Aplicacion principal Flask y rutas web
agent_worker.py         Worker autonomo para eventos en segundo plano
requirements.txt        Dependencias Python
README.md               Documentacion del proyecto

modules/
  agent.py              Flujo del agente de reclutamiento
  analyzer.py           Analisis de CV, habilidades y compatibilidad
  database.py           Persistencia SQLite y operaciones de datos
  email_sender.py       Envio real de correos por SMTP
  extractor.py          Extraccion de texto de PDF y DOCX
  file_utils.py         Utilidades de archivos y hashes
  matching.py           Emparejamiento de vacantes por area/carrera
  ollama_client.py      Integracion con Ollama local
  ranking.py            Calculo de estados y ranking
  recruitbot.py         Logica del chatbot RecruitBot
  reports.py            Generacion de reportes PDF y Excel

templates/              Vistas HTML
static/                 CSS, JavaScript y librerias frontend
database/               Base SQLite local
uploads/                CVs cargados
reports/                Reportes generados
logs/                   Logs del worker
tests/                  Pruebas automatizadas
outputs/                Entregables generados
```

## Roles del sistema

### Administrador / RRHH

Usuario demo:

```text
Correo: admin@demo.com
Contrasena: admin123
```

Despues de iniciar sesion entra a:

```text
/admin/dashboard
```

Puede:

- ver dashboard administrativo;
- crear, pausar, cerrar y seleccionar vacantes;
- ver candidatos;
- importar CVs externos;
- ejecutar/reprocesar analisis IA;
- ver ranking;
- abrir fichas inteligentes;
- aprobar o rechazar candidatos;
- generar invitaciones;
- enviar correos automaticos;
- generar reportes;
- revisar historial;
- supervisar el worker autonomo.

### Candidato

Todo usuario registrado desde la web recibe automaticamente el rol `candidato`.

Despues de iniciar sesion entra a:

```text
/candidato/dashboard
```

Puede:

- editar su perfil;
- subir o actualizar su CV;
- ver vacantes recomendadas para su area;
- ver otras vacantes disponibles;
- postular a una vacante;
- ver el estado de sus postulaciones;
- ver y responder invitaciones a entrevista.

El candidato no puede acceder a rutas administrativas.

### Agente IA

El agente IA no es un usuario del sistema. Funciona como proceso interno mediante:

- reglas de analisis;
- Ollama local opcional;
- cola de eventos;
- worker autonomo.

## Flujo general

1. RRHH crea una vacante y define habilidades, requisitos, area, carrera objetivo, pesos y umbrales.
2. Un candidato se registra y completa su perfil.
3. El candidato sube su CV.
4. El sistema guarda el archivo y encola un evento de preanalisis.
5. El worker autonomo procesa el evento.
6. El CV se compara contra las vacantes activas.
7. El candidato ve vacantes recomendadas segun su area/carrera.
8. El candidato postula a una vacante.
9. El worker analiza la postulacion.
10. RRHH revisa ranking y ficha inteligente.
11. RRHH aprueba o rechaza.
12. Si aprueba, el sistema prepara invitacion.
13. El worker envia el correo real por SMTP.
14. El candidato ve la invitacion y puede confirmarla o rechazarla.
15. Todo queda registrado en historial y eventos del agente.

## Analisis de CV

El analizador evalua:

- habilidades encontradas;
- habilidades faltantes;
- experiencia detectada;
- estudios detectados;
- compatibilidad porcentual;
- estado de recomendacion;
- justificacion;
- accion sugerida;
- fortalezas;
- brechas;
- preguntas de entrevista.

Cada vacante puede configurar:

- peso de habilidades;
- peso de experiencia;
- peso de estudios;
- umbral de preseleccion;
- umbral de observacion.

Estados posibles:

- `Preseleccionado`
- `En observacion`
- `No recomendado`

## Deteccion flexible de habilidades

El sistema no depende solamente de un catalogo fijo de habilidades.

Ahora la fuente principal son las habilidades escritas en cada vacante. Esto permite crear vacantes de distintas areas como:

- tecnologia;
- ingenieria civil;
- administracion;
- contabilidad;
- ventas;
- salud;
- educacion;
- derecho;
- arquitectura;
- otras areas.

El sistema combina:

- coincidencia exacta;
- alias y sinonimos conocidos;
- deteccion semantica opcional con Ollama.

Importante: Ollama solo puede marcar como detectadas habilidades que ya esten escritas en la vacante. Esto evita que el modelo invente habilidades.

## Ollama local

El sistema funciona sin Ollama usando reglas ponderadas. Si Ollama esta activo, mejora el analisis con deteccion semantica y explicaciones mas naturales.

Modelo recomendado:

```text
qwen2.5:3b
```

Instalacion del modelo:

```powershell
ollama pull qwen2.5:3b
```

Variables de entorno:

```powershell
$env:OLLAMA_ENABLED="1"
$env:OLLAMA_MODEL="qwen2.5:3b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
```

Si Ollama esta apagado o no responde, el sistema continua con el analizador por reglas.

## RecruitBot

RecruitBot es un chatbot flotante visible en la aplicacion.

Puede responder consultas sobre:

- mejor candidato;
- top 5 candidatos;
- vacantes;
- postulantes;
- aprobados;
- rechazados;
- entrevistas;
- decisiones del agente;
- preguntas de entrevista.

El endpoint usado por el chatbot es:

```text
POST /chatbot
```

RecruitBot usa contexto segun el rol:

- admin: contexto global de RRHH;
- candidato: solo su perfil, postulaciones, invitaciones y vacantes;
- publico: vacantes publicas.

Tambien detecta saludos y agradecimientos para no repetir consultas anteriores.

## Worker autonomo

El worker se ejecuta separado de Flask:

```powershell
python agent_worker.py
```

Eventos soportados:

- `PREANALIZAR_PERFIL`
- `ANALIZAR_POSTULACION`
- `ANALIZAR_IMPORTADOS`
- `REPROCESAR_VACANTE`
- `ENVIAR_CORREOS`

El worker:

- revisa la cola persistente en SQLite;
- detecta CVs nuevos en `uploads/`;
- evita duplicados por hash;
- procesa analisis;
- genera reportes;
- prepara acciones;
- envia correos en cola;
- registra errores;
- renueva bloqueos de eventos largos;
- guarda latido en la base de datos.

Para procesar solo un evento y salir:

```powershell
python agent_worker.py --once
```

## Envio real de correos

El envio SMTP se configura con variables de entorno.

Ejemplo para Gmail:

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="tu-correo@gmail.com"
$env:SMTP_PASSWORD="tu-contrasena-de-aplicacion"
$env:SMTP_FROM="tu-correo@gmail.com"
$env:SMTP_USE_TLS="1"
$env:SMTP_USE_SSL="0"
```

Para Gmail se debe usar una contrasena de aplicacion, no la contrasena normal de la cuenta.

No subas contrasenas reales al repositorio.

## Instalacion

Crear entorno virtual:

```powershell
python -m venv .venv
```

Activar entorno:

```powershell
.venv\Scripts\activate
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

## Ejecucion local

Iniciar Flask:

```powershell
python app.py
```

Abrir:

```text
http://127.0.0.1:5000
```

En otra terminal iniciar el worker:

```powershell
python agent_worker.py --poll-seconds 2
```

## Variables recomendadas

Para ejecucion local con Ollama y SMTP:

```powershell
$env:SECRET_KEY="cambia-esta-clave"
$env:OLLAMA_ENABLED="1"
$env:OLLAMA_MODEL="qwen2.5:3b"
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="tu-correo@gmail.com"
$env:SMTP_PASSWORD="tu-contrasena-de-aplicacion"
$env:SMTP_FROM="tu-correo@gmail.com"
$env:SMTP_USE_TLS="1"
$env:SMTP_USE_SSL="0"
python app.py
```

El worker debe iniciarse con las mismas variables si va a usar Ollama y enviar correos.

## Base de datos

La base local se crea automaticamente en:

```text
database/reclutamiento.db
```

Al iniciar, el sistema crea:

- tabla de usuarios;
- tabla de vacantes;
- tabla de candidatos;
- tabla de analisis;
- tabla de postulaciones;
- tabla de correos;
- tabla de historial;
- tabla de eventos del agente;
- tabla de estado del worker;
- tabla de alertas;
- tabla de decisiones RRHH.

Tambien crea automaticamente el usuario administrador demo si no existe.

## Pruebas

Ejecutar pruebas:

```powershell
python -m unittest discover -s tests -v
```

Ultima validacion realizada:

```text
Ran 32 tests
OK
```

## Recomendaciones antes de subir a Git

No subir informacion sensible ni archivos generados localmente.

Se recomienda ignorar:

```text
__pycache__/
*.pyc
.venv/
database/*.db
uploads/
reports/
logs/
*.log
.env
```

Si necesitas compartir ejemplos, usa archivos ficticios o anonimizados.

## Rutas principales

Publicas:

```text
/
/login
/registro
/register
/vacantes-publicas
/sobre-nosotros
```

Administrador:

```text
/admin/dashboard
/admin/vacantes
/admin/candidatos
/admin/carga-cvs
/admin/analisis
/admin/ranking
/admin/decision
/admin/agente
/admin/correos
/admin/reportes
/admin/historial
```

Candidato:

```text
/candidato/dashboard
/candidato/perfil
/candidato/mi-cv
/candidato/vacantes
/candidato/postulaciones
/candidato/invitaciones
```

## Estado actual del proyecto

El proyecto cuenta con:

- roles separados;
- analisis de CV por reglas y Ollama;
- deteccion flexible de habilidades por vacante;
- agente autonomo con worker;
- RecruitBot integrado;
- envio SMTP real;
- reportes PDF/Excel;
- pruebas automatizadas;
- flujo completo de postulacion y decision RRHH.

RecruitAI puede describirse como un sistema de reclutamiento inteligente con agente autonomo supervisado por RRHH.
