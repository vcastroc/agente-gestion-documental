import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "reclutamiento.db"


def _connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _rows(query, params=()):
    with _connection() as connection:
        return [dict(row) for row in connection.execute(query, params).fetchall()]


def _execute(query, params=()):
    with _connection() as connection:
        cursor = connection.execute(query, params)
        connection.commit()
        return cursor.lastrowid


def inicializar_bd():
    schema = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, correo TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL, rol TEXT NOT NULL DEFAULT 'candidato', telefono TEXT,
        universidad TEXT, carrera TEXT, ciudad TEXT, fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS vacantes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, empresa TEXT NOT NULL,
        area TEXT, carreras_objetivo TEXT, descripcion TEXT, requisitos TEXT, habilidades TEXT, experiencia INTEGER DEFAULT 0,
        estudios TEXT, fecha_entrevista TEXT, hora_entrevista TEXT, estado TEXT DEFAULT 'Activa',
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS candidatos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL, correo TEXT, telefono TEXT,
        archivo TEXT, universidad TEXT, carrera TEXT, ciudad TEXT, fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analisis (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidato_id INTEGER NOT NULL, vacante_id INTEGER NOT NULL,
        compatibilidad REAL NOT NULL, estado TEXT NOT NULL, habilidades_encontradas TEXT,
        habilidades_faltantes TEXT, fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidato_id) REFERENCES candidatos(id), FOREIGN KEY(vacante_id) REFERENCES vacantes(id)
    );
    CREATE TABLE IF NOT EXISTS correos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidato_id INTEGER, destinatario TEXT, asunto TEXT,
        mensaje TEXT, estado TEXT, fecha_envio TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(candidato_id) REFERENCES candidatos(id)
    );
    CREATE TABLE IF NOT EXISTS historial (
        id INTEGER PRIMARY KEY AUTOINCREMENT, evento TEXT NOT NULL, detalle TEXT,
        fecha TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS postulaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER NOT NULL, vacante_id INTEGER NOT NULL,
        estado TEXT NOT NULL DEFAULT 'Postulado', fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(usuario_id, vacante_id), FOREIGN KEY(usuario_id) REFERENCES usuarios(id),
        FOREIGN KEY(vacante_id) REFERENCES vacantes(id)
    );
    CREATE TABLE IF NOT EXISTS ejecuciones_agente (
        id INTEGER PRIMARY KEY AUTOINCREMENT, vacante_id INTEGER, origen TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'Pendiente', detalle TEXT,
        fecha_inicio TEXT DEFAULT CURRENT_TIMESTAMP, fecha_fin TEXT
    );
    CREATE TABLE IF NOT EXISTS eventos_agente (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, payload TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'Pendiente', intentos INTEGER NOT NULL DEFAULT 0,
        max_intentos INTEGER NOT NULL DEFAULT 3, disponible_desde TEXT DEFAULT CURRENT_TIMESTAMP,
        bloqueado_hasta TEXT, worker_id TEXT, ultimo_error TEXT,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP, fecha_actualizacion TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_eventos_agente_disponibles
        ON eventos_agente(estado, disponible_desde, id);
    CREATE TABLE IF NOT EXISTS estado_worker (
        id INTEGER PRIMARY KEY CHECK(id=1), worker_id TEXT, estado TEXT NOT NULL,
        ultimo_latido TEXT NOT NULL, detalle TEXT
    );
    CREATE TABLE IF NOT EXISTS alertas_agente (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, titulo TEXT NOT NULL,
        detalle TEXT, nivel TEXT NOT NULL DEFAULT 'info', referencia TEXT,
        leida INTEGER NOT NULL DEFAULT 0, fecha TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS decisiones_rrhh (
        id INTEGER PRIMARY KEY AUTOINCREMENT, candidato_id INTEGER NOT NULL, vacante_id INTEGER NOT NULL,
        estado TEXT NOT NULL, comentario TEXT, fecha TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(candidato_id, vacante_id), FOREIGN KEY(candidato_id) REFERENCES candidatos(id),
        FOREIGN KEY(vacante_id) REFERENCES vacantes(id)
    );
    """
    with _connection() as connection:
        connection.executescript(schema)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(usuarios)").fetchall()}
        if "cv_archivo" not in columns:
            connection.execute("ALTER TABLE usuarios ADD COLUMN cv_archivo TEXT")
        if "cv_hash" not in columns:
            connection.execute("ALTER TABLE usuarios ADD COLUMN cv_hash TEXT")
        candidate_columns = {row["name"] for row in connection.execute("PRAGMA table_info(candidatos)").fetchall()}
        if "usuario_id" not in candidate_columns:
            connection.execute("ALTER TABLE candidatos ADD COLUMN usuario_id INTEGER")
        if "archivo_hash" not in candidate_columns:
            connection.execute("ALTER TABLE candidatos ADD COLUMN archivo_hash TEXT")
        postulation_columns = {row["name"] for row in connection.execute("PRAGMA table_info(postulaciones)").fetchall()}
        if "compatibilidad" not in postulation_columns:
            connection.execute("ALTER TABLE postulaciones ADD COLUMN compatibilidad REAL")
        if "recomendacion_ia" not in postulation_columns:
            connection.execute("ALTER TABLE postulaciones ADD COLUMN recomendacion_ia TEXT")
        email_columns = {row["name"] for row in connection.execute("PRAGMA table_info(correos)").fetchall()}
        if "vacante_id" not in email_columns:
            connection.execute("ALTER TABLE correos ADD COLUMN vacante_id INTEGER")
        vacancy_columns = {row["name"] for row in connection.execute("PRAGMA table_info(vacantes)").fetchall()}
        for name, definition in (
            ("peso_habilidades", "INTEGER DEFAULT 70"),
            ("peso_experiencia", "INTEGER DEFAULT 20"),
            ("peso_estudios", "INTEGER DEFAULT 10"),
            ("umbral_preseleccion", "INTEGER DEFAULT 80"),
            ("umbral_observacion", "INTEGER DEFAULT 60"),
        ):
            if name not in vacancy_columns:
                connection.execute(f"ALTER TABLE vacantes ADD COLUMN {name} {definition}")
        if "carreras_objetivo" not in vacancy_columns:
            connection.execute("ALTER TABLE vacantes ADD COLUMN carreras_objetivo TEXT")
        analysis_columns = {row["name"] for row in connection.execute("PRAGMA table_info(analisis)").fetchall()}
        for name, definition in (
            ("experiencia_detectada", "INTEGER DEFAULT 0"),
            ("estudios_detectados", "TEXT"),
            ("desglose", "TEXT"),
            ("justificacion", "TEXT"),
            ("accion_sugerida", "TEXT"),
            ("resumen_profesional", "TEXT"),
            ("fortalezas", "TEXT"),
            ("brechas", "TEXT"),
            ("preguntas_entrevista", "TEXT"),
        ):
            if name not in analysis_columns:
                connection.execute(f"ALTER TABLE analisis ADD COLUMN {name} {definition}")
        connection.execute(
            """UPDATE correos SET vacante_id=(
                SELECT a.vacante_id FROM analisis a
                WHERE a.candidato_id=correos.candidato_id ORDER BY a.id DESC LIMIT 1
            ) WHERE vacante_id IS NULL"""
        )
    _crear_datos_demo()


def crear_usuario(nombre, correo, password, rol="candidato", telefono="", universidad="", carrera="", ciudad=""):
    return _execute(
        "INSERT INTO usuarios(nombre,correo,password,rol,telefono,universidad,carrera,ciudad) VALUES(?,?,?,?,?,?,?,?)",
        (nombre, correo, generate_password_hash(password), rol, telefono, universidad, carrera, ciudad),
    )


def obtener_usuario(correo):
    rows = _rows("SELECT * FROM usuarios WHERE correo=?", (correo,))
    return rows[0] if rows else None


def obtener_usuario_por_id(usuario_id):
    rows = _rows("SELECT * FROM usuarios WHERE id=?", (usuario_id,))
    return rows[0] if rows else None


def actualizar_perfil_usuario(usuario_id, data):
    return _execute(
        """UPDATE usuarios SET nombre=?, telefono=?, universidad=?, carrera=?, ciudad=?
        WHERE id=?""",
        (data["nombre"], data.get("telefono"), data.get("universidad"), data.get("carrera"),
         data.get("ciudad"), usuario_id),
    )


def guardar_cv_usuario(usuario_id, archivo, archivo_hash=None):
    result = _execute("UPDATE usuarios SET cv_archivo=?,cv_hash=? WHERE id=?", (archivo, archivo_hash, usuario_id))
    encolar_evento_agente("PREANALIZAR_PERFIL", {"usuario_id": usuario_id})
    return result


def guardar_vacante(data, encolar=True):
    vacante_id = _execute(
        """INSERT INTO vacantes(titulo,empresa,area,carreras_objetivo,descripcion,requisitos,habilidades,experiencia,estudios,
        fecha_entrevista,hora_entrevista,estado,peso_habilidades,peso_experiencia,peso_estudios,
        umbral_preseleccion,umbral_observacion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (data["titulo"], data["empresa"], data.get("area"), data.get("carreras_objetivo"),
         data.get("descripcion"), data.get("requisitos"), data.get("habilidades"), data.get("experiencia", 0), data.get("estudios"),
         data.get("fecha_entrevista"), data.get("hora_entrevista"), data.get("estado", "Activa"),
         data.get("peso_habilidades", 70), data.get("peso_experiencia", 20), data.get("peso_estudios", 10),
         data.get("umbral_preseleccion", 80), data.get("umbral_observacion", 60)),
    )
    guardar_evento_historial("Vacante creada", f"{data['titulo']} - {data['empresa']}")
    if encolar and data.get("estado", "Activa") == "Activa":
        encolar_evento_agente("REPROCESAR_VACANTE", {"vacante_id": vacante_id})
    return vacante_id


def obtener_vacantes(solo_activas=False):
    query = "SELECT * FROM vacantes"
    if solo_activas:
        query += " WHERE estado='Activa'"
    return _rows(query + " ORDER BY id DESC")


def obtener_vacante_por_id(vacante_id):
    rows = _rows("SELECT * FROM vacantes WHERE id=?", (vacante_id,))
    return rows[0] if rows else None


def actualizar_estado_vacante(vacante_id, estado):
    if estado not in {"Activa", "Pausada", "Cerrada"}:
        return False
    with _connection() as connection:
        cursor = connection.execute("UPDATE vacantes SET estado=? WHERE id=?", (estado, vacante_id))
        connection.commit()
    updated = bool(cursor.rowcount)
    if updated and estado == "Activa":
        encolar_evento_agente("REPROCESAR_VACANTE", {"vacante_id": vacante_id})
    return updated


def guardar_candidato(data):
    candidate_id = _execute(
        """INSERT INTO candidatos(nombre,correo,telefono,archivo,universidad,carrera,ciudad,usuario_id,archivo_hash)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (data["nombre"], data.get("correo"), data.get("telefono"), data.get("archivo"),
         data.get("universidad"), data.get("carrera"), data.get("ciudad"), data.get("usuario_id"),
         data.get("archivo_hash")),
    )
    guardar_evento_historial("CV cargado", data["nombre"])
    return candidate_id


def obtener_candidatos():
    return _rows("SELECT * FROM candidatos ORDER BY id DESC")


def obtener_archivos_cv_registrados():
    rows = _rows(
        """SELECT archivo AS nombre FROM candidatos WHERE archivo IS NOT NULL
        UNION SELECT cv_archivo AS nombre FROM usuarios WHERE cv_archivo IS NOT NULL"""
    )
    return {row["nombre"] for row in rows}


def existe_hash_cv(archivo_hash):
    if not archivo_hash:
        return False
    rows = _rows(
        """SELECT 1 FROM candidatos WHERE archivo_hash=?
        UNION SELECT 1 FROM usuarios WHERE cv_hash=? LIMIT 1""",
        (archivo_hash, archivo_hash),
    )
    return bool(rows)


def obtener_candidato_por_usuario(usuario_id):
    rows = _rows("SELECT * FROM candidatos WHERE usuario_id=? ORDER BY id DESC LIMIT 1", (usuario_id,))
    return rows[0] if rows else None


def actualizar_candidato_extraido(candidato_id, result):
    return _execute(
        """UPDATE candidatos SET nombre=?, correo=COALESCE(NULLIF(?, ''), correo),
        telefono=COALESCE(NULLIF(?, ''), telefono) WHERE id=?""",
        (result["nombre"], result.get("correo"), result.get("telefono"), candidato_id),
    )


def crear_o_actualizar_candidato_usuario(usuario):
    candidate = obtener_candidato_por_usuario(usuario["id"])
    data = (
        usuario["nombre"], usuario["correo"], usuario.get("telefono"), usuario.get("cv_archivo"),
        usuario.get("universidad"), usuario.get("carrera"), usuario.get("ciudad"), usuario["id"],
        usuario.get("cv_hash"),
    )
    if candidate:
        _execute(
            """UPDATE candidatos SET nombre=?,correo=?,telefono=?,archivo=?,universidad=?,carrera=?,ciudad=?,archivo_hash=?
            WHERE usuario_id=?""",
            data[:-2] + (data[-1], data[-2]),
        )
        return candidate["id"]
    return guardar_candidato({
        "nombre": usuario["nombre"], "correo": usuario["correo"], "telefono": usuario.get("telefono"),
        "archivo": usuario.get("cv_archivo"), "universidad": usuario.get("universidad"),
        "carrera": usuario.get("carrera"), "ciudad": usuario.get("ciudad"), "usuario_id": usuario["id"],
        "archivo_hash": usuario.get("cv_hash"),
    })


def guardar_analisis(candidato_id, vacante_id, result):
    analysis_id = _execute(
        """INSERT INTO analisis(candidato_id,vacante_id,compatibilidad,estado,habilidades_encontradas,
        habilidades_faltantes,experiencia_detectada,estudios_detectados,desglose,justificacion,accion_sugerida,
        resumen_profesional,fortalezas,brechas,preguntas_entrevista)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (candidato_id, vacante_id, result["compatibilidad"], result["estado"],
         json.dumps(result["habilidades_encontradas"], ensure_ascii=False),
         json.dumps(result["habilidades_faltantes"], ensure_ascii=False),
         result.get("experiencia_detectada", 0), result.get("estudios_detectados"),
         json.dumps(result.get("desglose", {}), ensure_ascii=False),
         result.get("justificacion"), result.get("accion_sugerida"), result.get("resumen_profesional"),
         json.dumps(result.get("fortalezas", []), ensure_ascii=False),
         json.dumps(result.get("brechas", []), ensure_ascii=False),
         json.dumps(result.get("preguntas_entrevista", []), ensure_ascii=False)),
    )
    guardar_evento_historial("Análisis realizado", f"Candidato #{candidato_id}: {result['compatibilidad']}%")
    if result["compatibilidad"] >= 85:
        guardar_alerta_agente(
            "Candidato destacado", "Nuevo perfil con alta compatibilidad",
            f"Candidato #{candidato_id} alcanzó {result['compatibilidad']}% para la vacante #{vacante_id}.",
            "success", f"destacado:{candidato_id}:{vacante_id}",
        )
    return analysis_id


def eliminar_analisis_candidato_vacante(candidato_id, vacante_id):
    return _execute("DELETE FROM analisis WHERE candidato_id=? AND vacante_id=?", (candidato_id, vacante_id))


def obtener_ranking(vacante_id=None):
    query = """SELECT a.*, c.nombre, c.correo, c.telefono, v.titulo AS vacante,
               d.estado AS decision_rrhh, d.comentario AS comentario_rrhh
               FROM analisis a JOIN candidatos c ON c.id=a.candidato_id
               JOIN vacantes v ON v.id=a.vacante_id
               LEFT JOIN decisiones_rrhh d ON d.candidato_id=a.candidato_id AND d.vacante_id=a.vacante_id"""
    params = ()
    if vacante_id:
        query += " WHERE a.vacante_id=?"
        params = (vacante_id,)
    query += " ORDER BY a.compatibilidad DESC, a.id DESC"
    rows = _rows(query, params)
    for row in rows:
        row["habilidades_encontradas"] = ", ".join(json.loads(row["habilidades_encontradas"] or "[]"))
        row["habilidades_faltantes"] = ", ".join(json.loads(row["habilidades_faltantes"] or "[]"))
        row["desglose"] = json.loads(row.get("desglose") or "{}")
        row["fortalezas"] = json.loads(row.get("fortalezas") or "[]")
        row["brechas"] = json.loads(row.get("brechas") or "[]")
        row["preguntas_entrevista"] = json.loads(row.get("preguntas_entrevista") or "[]")
    return rows


def obtener_analisis_por_id(analisis_id):
    rows = _rows(
        """SELECT a.*, c.nombre, c.correo, c.telefono, v.titulo AS vacante, v.empresa
        FROM analisis a JOIN candidatos c ON c.id=a.candidato_id
        JOIN vacantes v ON v.id=a.vacante_id WHERE a.id=?""",
        (analisis_id,),
    )
    if not rows:
        return None
    row = rows[0]
    row["habilidades_encontradas"] = json.loads(row["habilidades_encontradas"] or "[]")
    row["habilidades_faltantes"] = json.loads(row["habilidades_faltantes"] or "[]")
    row["desglose"] = json.loads(row.get("desglose") or "{}")
    row["fortalezas"] = json.loads(row.get("fortalezas") or "[]")
    row["brechas"] = json.loads(row.get("brechas") or "[]")
    row["preguntas_entrevista"] = json.loads(row.get("preguntas_entrevista") or "[]")
    return row


def guardar_decision_rrhh(candidato_id, vacante_id, estado, comentario=""):
    if estado not in {"Aprobado", "Rechazado", "Pendiente"}:
        return False
    _execute(
        """INSERT INTO decisiones_rrhh(candidato_id,vacante_id,estado,comentario,fecha)
        VALUES(?,?,?,?,?) ON CONFLICT(candidato_id,vacante_id) DO UPDATE SET
        estado=excluded.estado, comentario=excluded.comentario, fecha=excluded.fecha""",
        (candidato_id, vacante_id, estado, comentario, _db_timestamp()),
    )
    candidate = _rows("SELECT usuario_id,nombre FROM candidatos WHERE id=?", (candidato_id,))
    if candidate and candidate[0].get("usuario_id"):
        final_state = "Entrevista aprobada por RRHH" if estado == "Aprobado" else (
            "Proceso finalizado por RRHH" if estado == "Rechazado" else "En revision por RRHH"
        )
        _execute(
            "UPDATE postulaciones SET estado=? WHERE usuario_id=? AND vacante_id=?",
            (final_state, candidate[0]["usuario_id"], vacante_id),
        )
    guardar_evento_historial(
        "Decision final de RRHH", f"Candidato #{candidato_id} - Vacante #{vacante_id}: {estado}. {comentario}".strip(),
    )
    return True


def guardar_correo(candidato_id, destinatario, asunto, mensaje, estado, vacante_id=None):
    email_id = _execute(
        """INSERT INTO correos(candidato_id,destinatario,asunto,mensaje,estado,fecha_envio,vacante_id)
        VALUES(?,?,?,?,?,?,?)""",
        (candidato_id, destinatario, asunto, mensaje, estado, datetime.now().isoformat(timespec="seconds"), vacante_id),
    )
    evento = "Correo preparado" if estado == "Borrador" else "Correo enviado"
    guardar_evento_historial(evento, f"{destinatario} - {estado}")
    return email_id


def guardar_borrador_correo(candidato_id, destinatario, asunto, mensaje, vacante_id):
    rows = _rows(
        """SELECT id FROM correos WHERE candidato_id=? AND destinatario=? AND asunto=?
        AND vacante_id=? AND estado IN ('Borrador','En cola','Enviado','Confirmada','Rechazada')""",
        (candidato_id, destinatario, asunto, vacante_id),
    )
    if rows:
        return rows[0]["id"]
    return guardar_correo(candidato_id, destinatario, asunto, mensaje, "Borrador", vacante_id)


def obtener_correos(vacante_id=None):
    if vacante_id:
        return _rows("SELECT * FROM correos WHERE vacante_id=? ORDER BY id DESC", (vacante_id,))
    return _rows("SELECT * FROM correos ORDER BY id DESC")


def obtener_borradores_correo(vacante_id=None):
    query = "SELECT * FROM correos WHERE estado='Borrador'"
    params = []
    if vacante_id:
        query += " AND vacante_id=?"
        params.append(vacante_id)
    return _rows(query + " ORDER BY id", tuple(params))


def marcar_correo_enviado(correo_id):
    return _execute(
        "UPDATE correos SET estado='Enviado', fecha_envio=? WHERE id=? AND estado IN ('Borrador','En cola')",
        (datetime.now().isoformat(timespec="seconds"), correo_id),
    )


def aprobar_borradores_correo(vacante_id):
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE correos SET estado='En cola' WHERE vacante_id=? AND estado='Borrador'",
            (vacante_id,),
        )
        connection.commit()
    if cursor.rowcount:
        encolar_evento_agente("ENVIAR_CORREOS", {"vacante_id": vacante_id})
        guardar_evento_historial("Correos aprobados por RRHH", f"{cursor.rowcount} correo(s) enviados a la cola")
    return cursor.rowcount


def obtener_correos_en_cola(vacante_id=None):
    query = "SELECT * FROM correos WHERE estado='En cola'"
    params = []
    if vacante_id:
        query += " AND vacante_id=?"
        params.append(vacante_id)
    return _rows(query + " ORDER BY id", tuple(params))


def guardar_postulacion(usuario_id, vacante_id):
    if not obtener_vacante_por_id(vacante_id):
        return None
    try:
        postulation_id = _execute(
            "INSERT INTO postulaciones(usuario_id,vacante_id) VALUES(?,?)",
            (usuario_id, vacante_id),
        )
        guardar_evento_historial("Postulación registrada", f"Usuario #{usuario_id} - Vacante #{vacante_id}")
        encolar_evento_agente("ANALIZAR_POSTULACION", {"usuario_id": usuario_id, "vacante_id": vacante_id})
        return postulation_id
    except sqlite3.IntegrityError:
        return None


def obtener_postulaciones_usuario(usuario_id):
    return _rows(
        """SELECT p.*, v.titulo, v.empresa, v.area
        FROM postulaciones p JOIN vacantes v ON v.id=p.vacante_id
        WHERE p.usuario_id=? ORDER BY p.id DESC""",
        (usuario_id,),
    )


def obtener_recomendaciones_usuario(usuario_id):
    return _rows(
        """SELECT a.compatibilidad, a.estado, a.justificacion, v.id AS vacante_id,
        v.titulo, v.empresa, v.area
        FROM candidatos c JOIN analisis a ON a.candidato_id=c.id
        JOIN vacantes v ON v.id=a.vacante_id
        WHERE c.usuario_id=? AND v.estado='Activa'
        ORDER BY a.compatibilidad DESC""",
        (usuario_id,),
    )


def actualizar_postulacion(usuario_id, vacante_id, compatibilidad, recomendacion_ia):
    return _execute(
        """UPDATE postulaciones SET compatibilidad=?, recomendacion_ia=?, estado='En revision por RRHH'
        WHERE usuario_id=? AND vacante_id=?""",
        (compatibilidad, recomendacion_ia, usuario_id, vacante_id),
    )


def obtener_invitaciones_usuario(correo):
    return _rows(
        """SELECT co.*, c.nombre, v.titulo AS vacante, v.fecha_entrevista, v.hora_entrevista
        FROM correos co LEFT JOIN candidatos c ON c.id=co.candidato_id
        LEFT JOIN vacantes v ON v.id=co.vacante_id
        WHERE co.destinatario=? AND co.estado IN ('Enviado','Confirmada','Rechazada')
        ORDER BY co.id DESC""",
        (correo,),
    )


def actualizar_estado_invitacion(correo, correo_id, estado):
    if estado not in {"Confirmada", "Rechazada"}:
        return False
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE correos SET estado=? WHERE id=? AND destinatario=?",
            (estado, correo_id, correo),
        )
        connection.commit()
    if cursor.rowcount:
        guardar_evento_historial("Invitación actualizada", f"{correo} - {estado}")
        return True
    return False


def guardar_evento_historial(evento, detalle=""):
    return _execute("INSERT INTO historial(evento,detalle) VALUES(?,?)", (evento, detalle))


def obtener_historial(limit=100):
    return _rows("SELECT * FROM historial ORDER BY id DESC LIMIT ?", (limit,))


def crear_ejecucion_agente(vacante_id, origen):
    execution_id = _execute(
        "INSERT INTO ejecuciones_agente(vacante_id,origen,estado) VALUES(?,?,?)",
        (vacante_id, origen, "Analizando"),
    )
    guardar_evento_historial("Agente iniciado", f"Ejecución #{execution_id} - {origen}")
    return execution_id


def finalizar_ejecucion_agente(ejecucion_id, estado, detalle):
    _execute(
        "UPDATE ejecuciones_agente SET estado=?, detalle=?, fecha_fin=? WHERE id=?",
        (estado, detalle, datetime.now().isoformat(timespec="seconds"), ejecucion_id),
    )
    guardar_evento_historial("Agente finalizado", f"Ejecución #{ejecucion_id} - {estado}: {detalle}")


def obtener_ejecuciones_agente(limit=10):
    return _rows(
        """SELECT e.*, v.titulo AS vacante FROM ejecuciones_agente e
        LEFT JOIN vacantes v ON v.id=e.vacante_id ORDER BY e.id DESC LIMIT ?""",
        (limit,),
    )


def _db_timestamp(seconds=0):
    return (datetime.now() + timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")


def encolar_evento_agente(tipo, payload, max_intentos=3):
    event_id = _execute(
        """INSERT INTO eventos_agente(tipo,payload,max_intentos,disponible_desde,fecha_creacion,fecha_actualizacion)
        VALUES(?,?,?,?,?,?)""",
        (tipo, json.dumps(payload, ensure_ascii=False), max_intentos, _db_timestamp(), _db_timestamp(), _db_timestamp()),
    )
    guardar_evento_historial("Evento encolado", f"Evento #{event_id} - {tipo}")
    return event_id


def reclamar_evento_agente(worker_id, lease_seconds=60):
    now = _db_timestamp()
    with _connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """UPDATE eventos_agente SET estado='Pendiente', worker_id=NULL, bloqueado_hasta=NULL,
            fecha_actualizacion=? WHERE estado='Procesando' AND bloqueado_hasta < ?""",
            (now, now),
        )
        row = connection.execute(
            """SELECT * FROM eventos_agente WHERE estado='Pendiente' AND disponible_desde <= ?
            ORDER BY id LIMIT 1""",
            (now,),
        ).fetchone()
        if not row:
            connection.commit()
            return None
        event = dict(row)
        connection.execute(
            """UPDATE eventos_agente SET estado='Procesando', intentos=intentos+1, worker_id=?,
            bloqueado_hasta=?, fecha_actualizacion=? WHERE id=?""",
            (worker_id, _db_timestamp(lease_seconds), now, event["id"]),
        )
        connection.commit()
    event["intentos"] += 1
    event["payload"] = json.loads(event["payload"])
    return event


def renovar_bloqueo_evento(evento_id, worker_id, lease_seconds=60):
    with _connection() as connection:
        cursor = connection.execute(
            """UPDATE eventos_agente SET bloqueado_hasta=?,fecha_actualizacion=?
            WHERE id=? AND estado='Procesando' AND worker_id=?""",
            (_db_timestamp(lease_seconds), _db_timestamp(), evento_id, worker_id),
        )
        connection.commit()
    return bool(cursor.rowcount)


def completar_evento_agente(evento_id):
    return _execute(
        """UPDATE eventos_agente SET estado='Completado', bloqueado_hasta=NULL, ultimo_error=NULL,
        fecha_actualizacion=? WHERE id=?""",
        (_db_timestamp(), evento_id),
    )


def fallar_evento_agente(evento_id, error, retry_seconds=5):
    with _connection() as connection:
        row = connection.execute(
            "SELECT intentos,max_intentos FROM eventos_agente WHERE id=?",
            (evento_id,),
        ).fetchone()
        if not row:
            return
        state = "Error" if row["intentos"] >= row["max_intentos"] else "Pendiente"
        connection.execute(
            """UPDATE eventos_agente SET estado=?, disponible_desde=?, bloqueado_hasta=NULL,
            ultimo_error=?, fecha_actualizacion=? WHERE id=?""",
            (state, _db_timestamp(retry_seconds), str(error)[:500], _db_timestamp(), evento_id),
        )
        connection.commit()
    return state


def obtener_eventos_agente(limit=10):
    return _rows("SELECT * FROM eventos_agente ORDER BY id DESC LIMIT ?", (limit,))


def reintentar_evento_agente(evento_id):
    with _connection() as connection:
        cursor = connection.execute(
            """UPDATE eventos_agente SET estado='Pendiente', intentos=0, disponible_desde=?,
            bloqueado_hasta=NULL, worker_id=NULL, ultimo_error=NULL, fecha_actualizacion=?
            WHERE id=? AND estado='Error'""",
            (_db_timestamp(), _db_timestamp(), evento_id),
        )
        connection.commit()
    if cursor.rowcount:
        guardar_evento_historial("Evento reintentado", f"Evento #{evento_id} reenviado a la cola por RRHH")
    return bool(cursor.rowcount)


def obtener_resumen_eventos_agente():
    summary = {"Pendiente": 0, "Procesando": 0, "Completado": 0, "Error": 0}
    for row in _rows("SELECT estado,COUNT(*) AS total FROM eventos_agente GROUP BY estado"):
        summary[row["estado"]] = row["total"]
    return summary


def guardar_alerta_agente(tipo, titulo, detalle="", nivel="info", referencia=None):
    if referencia:
        rows = _rows("SELECT id FROM alertas_agente WHERE referencia=? AND leida=0", (referencia,))
        if rows:
            return rows[0]["id"]
    return _execute(
        "INSERT INTO alertas_agente(tipo,titulo,detalle,nivel,referencia) VALUES(?,?,?,?,?)",
        (tipo, titulo, detalle, nivel, referencia),
    )


def obtener_alertas_agente(limit=20, solo_no_leidas=False):
    query = "SELECT * FROM alertas_agente"
    if solo_no_leidas:
        query += " WHERE leida=0"
    return _rows(query + " ORDER BY id DESC LIMIT ?", (limit,))


def contar_alertas_agente():
    rows = _rows("SELECT COUNT(*) AS total FROM alertas_agente WHERE leida=0")
    return rows[0]["total"]


def marcar_alerta_agente_leida(alerta_id):
    return _execute("UPDATE alertas_agente SET leida=1 WHERE id=?", (alerta_id,))


def marcar_alertas_agente_leidas():
    return _execute("UPDATE alertas_agente SET leida=1 WHERE leida=0")


def actualizar_latido_worker(worker_id, estado="Activo", detalle="Esperando eventos"):
    now = _db_timestamp()
    return _execute(
        """INSERT INTO estado_worker(id,worker_id,estado,ultimo_latido,detalle) VALUES(1,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET worker_id=excluded.worker_id, estado=excluded.estado,
        ultimo_latido=excluded.ultimo_latido, detalle=excluded.detalle""",
        (worker_id, estado, now, detalle),
    )


def obtener_estado_worker(max_age_seconds=15):
    rows = _rows("SELECT * FROM estado_worker WHERE id=1")
    if not rows:
        return {"estado": "No iniciado", "activo": False, "detalle": "Ejecuta python agent_worker.py"}
    worker = rows[0]
    last_heartbeat = datetime.strptime(worker["ultimo_latido"], "%Y-%m-%d %H:%M:%S")
    worker["activo"] = datetime.now() - last_heartbeat <= timedelta(seconds=max_age_seconds)
    if not worker["activo"]:
        worker["estado"] = "Sin conexión"
    return worker


def _crear_datos_demo():
    if not obtener_usuario("admin@demo.com"):
        try:
            crear_usuario("Administrador Demo", "admin@demo.com", "admin123", "admin")
        except sqlite3.IntegrityError:
            # Another app process can seed the demo user during Flask reload.
            pass
    if not obtener_vacantes():
        guardar_vacante({
            "titulo": "Analista de Sistemas", "empresa": "TechNova", "area": "Tecnología",
            "descripcion": "Análisis y mejora de soluciones internas.",
            "requisitos": "Conocimientos de desarrollo y análisis de datos.",
            "habilidades": "Python, SQL, Git, Excel, Power BI, Trabajo en equipo",
            "experiencia": 1, "estudios": "Universitario", "fecha_entrevista": "2026-06-10",
            "hora_entrevista": "10:00",
        }, encolar=False)
    return
    if not obtener_candidatos():
        candidates = [
            ("Ana Torres", "ana.torres@demo.com", "Python, SQL, Git, Excel, Power BI, Trabajo en equipo", 100),
            ("Luis Mendoza", "luis.mendoza@demo.com", "Python, SQL, Git, Excel", 67),
            ("Carla Ruiz", "carla.ruiz@demo.com", "Excel, Comunicación", 17),
        ]
        vacante_id = obtener_vacantes()[0]["id"]
        for name, email, skills, score in candidates:
            candidate_id = guardar_candidato({"nombre": name, "correo": email, "archivo": "demo"})
            guardar_analisis(candidate_id, vacante_id, {
                "compatibilidad": score,
                "estado": "Preseleccionado" if score >= 80 else ("En observación" if score >= 60 else "No recomendado"),
                "habilidades_encontradas": [item.strip() for item in skills.split(",")],
                "habilidades_faltantes": [],
            })
        guardar_evento_historial("Ranking generado", "Ranking demo inicial")
