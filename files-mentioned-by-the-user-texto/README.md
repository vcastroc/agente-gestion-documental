# Agente Autónomo de Reclutamiento Inteligente

Aplicación web Flask para gestionar vacantes, cargar CVs, analizar compatibilidad,
generar un ranking explicable, enviar correos de entrevista y exportar reportes.
La información se guarda localmente en SQLite y no requiere APIs externas.

## Integrantes

- Vane: Interfaz, arquitectura y flujo del agente
- Xio: Extracción, NLP y compatibilidad
- Sandra: Ranking, correos, reportes e historial

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
python app.py
```

Abrir `http://127.0.0.1:5000`. La ruta inicial muestra la landing pública.

En otra terminal, iniciar el proceso autónomo:

```bash
python agent_worker.py
```

El panel web y el worker son procesos independientes. Si el worker se reinicia,
continúa con los eventos pendientes guardados en SQLite. Para procesar como máximo
un evento y salir, usar `python agent_worker.py --once`.

Para un despliegue fuera de la demo local, definir una clave privada:

```powershell
$env:SECRET_KEY="una-clave-segura-y-unica"
python app.py
```

Usuario administrador de demostración:

```text
admin@demo.com
admin123
```

## Roles

- Administrador RRHH: administra vacantes, candidatos, análisis IA, ranking,
  decisiones, correos, reportes e historial desde `/admin/dashboard`.
- Candidato: gestiona su perfil y CV, consulta vacantes, registra postulaciones y
  revisa invitaciones desde `/candidato/dashboard`.
- Público: consulta la portada, información del proyecto y vacantes disponibles
  antes de iniciar sesión o registrarse.

Las cuentas creadas desde el registro web siempre reciben el rol `candidato`.
El agente IA funciona internamente y no es un usuario del sistema.

## Flujo autónomo

1. Percibe: recibe CVs en PDF o DOCX, perfiles, postulaciones y vacantes.
2. Razona: extrae información y compara habilidades automáticamente.
3. Decide: calcula compatibilidad, estados y ranking.
4. Actúa: prepara reportes y borradores de correo.
5. Retroalimenta: guarda cada ejecución y evento en el historial.

La interfaz registra eventos cuando RRHH importa CVs externos, solicita un
reproceso, reactiva una vacante o cuando un candidato sube su CV personal o se
postula. El worker también detecta archivos PDF o DOCX copiados directamente en
`uploads/`. `agent_worker.py` procesa esos eventos desde la cola persistente,
fuera del ciclo HTTP, y reintenta los fallos. La subida de CV genera un
preanálisis orientativo contra las vacantes activas sin postular automáticamente
al usuario. RRHH conserva la aprobación final antes del envío real de correos.

## Envío real de correos

El envío SMTP se configura con variables de entorno. Por ejemplo, para Gmail:

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="tu-cuenta@gmail.com"
$env:SMTP_PASSWORD="tu-contraseña-de-aplicación"
$env:SMTP_FROM="tu-cuenta@gmail.com"
$env:SMTP_USE_TLS="1"
python app.py
```

Para Gmail se debe utilizar una contraseña de aplicación, no la contraseña
principal de la cuenta. El panel desactiva el botón de envío mientras no exista
una configuración SMTP válida. Los borradores que fallen permanecen pendientes.

Cada vacante permite configurar pesos para habilidades, experiencia y estudios,
además de umbrales de preselección y observación. Las decisiones guardan
justificación, evidencia y acción sugerida.

## Análisis local opcional con Ollama

El sistema funciona sin servicios externos mediante reglas ponderadas. De forma
opcional, Ollama puede enriquecer localmente la justificación y reconocer
habilidades complementarias sin modificar la puntuación determinística.

Después de instalar Ollama y descargar un modelo:

```powershell
ollama pull qwen2.5:3b
$env:OLLAMA_ENABLED="1"
$env:OLLAMA_MODEL="qwen2.5:3b"
python app.py
```

El worker también debe iniciarse con esas variables de entorno. Si Ollama está
apagado, responde con JSON inválido o tarda demasiado, el sistema continúa con
el analizador de respaldo. El dashboard RRHH muestra el estado de Ollama.

Cada análisis nuevo genera una ficha inteligente accesible desde el ranking:
resumen profesional, fortalezas, brechas y preguntas personalizadas para la
entrevista. Estas fichas también cuentan con un respaldo basado en reglas.

## Centro de control del agente

RRHH puede supervisar el proceso desde `/admin/agente`. La pantalla muestra el
latido del worker, el estado de Ollama, la cola persistente, alertas internas y
errores. Los eventos que agotaron sus intentos pueden reenviarse manualmente a la
cola. El agente crea alertas cuando detecta perfiles con compatibilidad alta o
cuando una tarea requiere atención.

## Estructura

```text
app.py                  Aplicación y rutas Flask
agent_worker.py         Worker autónomo, scheduler y procesamiento de eventos
modules/                Persistencia, extracción, análisis, ranking y reportes
templates/              Pantallas HTML
static/                 CSS y JavaScript
uploads/                CVs cargados
reports/                Archivos Excel y PDF generados
database/               Base de datos SQLite creada al iniciar
logs/                   Registro de actividad del worker
```

La aplicación crea automáticamente las carpetas necesarias, inicializa SQLite y
carga una vacante y tres candidatos demo en el primer inicio.

Bootstrap y Bootstrap Icons se incluyen dentro de `static/vendor/`, por lo que la
interfaz funciona sin conexión después de instalar las dependencias Python.

## Pruebas

```bash
python -m unittest discover -s tests -v
```
