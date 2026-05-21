from conexion import conectar
from datetime import datetime, timedelta
import hashlib

# ===== USUARIOS =====

def registrar_usuario(nombre, email, contrasena):
    conn = conectar()
    if not conn:
        return False, "Error de conexion"
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return False, "El correo ya esta registrado"
    h = hashlib.sha256(contrasena.encode()).hexdigest()
    cursor.execute("INSERT INTO usuarios (nombre, email, contrasena) VALUES (%s, %s, %s)",
                   (nombre, email, h))
    conn.commit()
    cursor.close()
    conn.close()
    return True, "Usuario registrado exitosamente"

def obtener_usuario_por_email(email):
    conn = conectar()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    u = cursor.fetchone()
    cursor.close()
    conn.close()
    return u

def actualizar_contrasena(id_usuario, nueva_contrasena):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    h = hashlib.sha256(nueva_contrasena.encode()).hexdigest()
    cursor.execute("UPDATE usuarios SET contrasena = %s WHERE id_usuario = %s", (h, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def login_usuario(email, contrasena):
    conn = conectar()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    h = hashlib.sha256(contrasena.encode()).hexdigest()
    cursor.execute("SELECT * FROM usuarios WHERE email = %s AND contrasena = %s", (email, h))
    u = cursor.fetchone()
    cursor.close()
    conn.close()
    return u

# ===== MATERIAS =====

def listar_materias(id_usuario):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM materias WHERE id_usuario = %s ORDER BY nombre", (id_usuario,))
    r = cursor.fetchall()
    cursor.close()
    conn.close()
    return r

def crear_materia(id_usuario, nombre, profesor="", color="#3498db"):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("INSERT INTO materias (id_usuario, nombre, profesor, color) VALUES (%s, %s, %s, %s)",
                   (id_usuario, nombre, profesor, color))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def editar_materia(id_materia, id_usuario, nombre, profesor, color):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("UPDATE materias SET nombre=%s, profesor=%s, color=%s WHERE id_materia=%s AND id_usuario=%s",
                   (nombre, profesor, color, id_materia, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def eliminar_materia(id_materia, id_usuario):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM materias WHERE id_materia=%s AND id_usuario=%s", (id_materia, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

# ===== TAREAS =====

def calcular_prioridad(fecha_limite, dificultad):
    hoy = datetime.now().date()
    f = datetime.strptime(str(fecha_limite)[:10], "%Y-%m-%d").date()
    dias = (f - hoy).days
    d = {"baja": 1, "media": 2, "alta": 3}
    p = d.get(dificultad, 2)
    if dias <= 1:
        return p * 10
    elif dias <= 3:
        return p * 7
    elif dias <= 7:
        return p * 4
    elif dias <= 14:
        return p * 2
    return p

def listar_tareas(id_usuario, filtro=None):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    sql = "SELECT * FROM tareas WHERE id_usuario = %s"
    params = [id_usuario]
    if filtro == "pendientes":
        sql += " AND estado = 'pendiente'"
    elif filtro == "completadas":
        sql += " AND estado = 'completada'"
    elif filtro == "vencidas":
        sql += " AND fecha_limite < CURDATE() AND estado = 'pendiente'"
    sql += " ORDER BY fecha_limite ASC"
    cursor.execute(sql, tuple(params))
    r = cursor.fetchall()
    for t in r:
        if isinstance(t.get("fecha_limite"), datetime):
            t["fecha_limite"] = t["fecha_limite"].strftime("%Y-%m-%d")
        t["prioridad"] = calcular_prioridad(t.get("fecha_limite", ""), t.get("dificultad", "media"))
    cursor.close()
    conn.close()
    return r

def crear_tarea(id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado):
    conn = conectar()
    if not conn:
        return False, "Error de conexion"
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO tareas (id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado)
                      VALUES (%s, %s, %s, %s, %s, %s)""",
                   (id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado))
    conn.commit()
    cursor.close()
    conn.close()

    crear_recordatorio_vencimiento(id_usuario, titulo, fecha_limite)
    return True, "Tarea creada exitosamente"

def editar_tarea(id_tarea, id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("""UPDATE tareas SET titulo=%s, descripcion=%s, fecha_limite=%s,
                      dificultad=%s, tiempo_estimado=%s
                      WHERE id_tarea=%s AND id_usuario=%s""",
                   (titulo, descripcion, fecha_limite, dificultad, tiempo_estimado, id_tarea, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def eliminar_tarea(id_tarea, id_usuario):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tareas WHERE id_tarea=%s AND id_usuario=%s", (id_tarea, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def completar_tarea(id_tarea, id_usuario):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("UPDATE tareas SET estado='completada' WHERE id_tarea=%s AND id_usuario=%s", (id_tarea, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def actualizar_tareas_vencidas():
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    cursor.execute("UPDATE tareas SET estado='pendiente' WHERE fecha_limite < CURDATE() AND estado='pendiente'")
    conn.commit()
    cursor.close()
    conn.close()

# ===== NOTAS =====

def listar_notas(id_usuario):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT n.*, m.nombre as materia_nombre
                      FROM notas n JOIN materias m ON n.id_materia = m.id_materia
                      WHERE n.id_usuario = %s ORDER BY n.fecha_registro DESC""", (id_usuario,))
    r = cursor.fetchall()
    cursor.close()
    conn.close()
    return r

def crear_nota(id_usuario, id_materia, calificacion, descripcion=""):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notas (id_usuario, id_materia, calificacion, descripcion) VALUES (%s, %s, %s, %s)",
                   (id_usuario, id_materia, calificacion, descripcion))
    conn.commit()
    cursor.close()
    conn.close()
    return True

# ===== HORARIOS =====

def listar_horarios(id_usuario):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT * FROM horarios WHERE id_usuario = %s
                      ORDER BY FIELD(dia_semana,'lunes','martes','miercoles','jueves','viernes','sabado','domingo'), hora_inicio""", (id_usuario,))
    r = cursor.fetchall()
    for h in r:
        if isinstance(h.get("hora_inicio"), timedelta):
            h["hora_inicio"] = (datetime.min + h["hora_inicio"]).strftime("%H:%M")
        if isinstance(h.get("hora_fin"), timedelta):
            h["hora_fin"] = (datetime.min + h["hora_fin"]).strftime("%H:%M")
    cursor.close()
    conn.close()
    return r

def crear_horario(id_usuario, dia_semana, hora_inicio, hora_fin):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("INSERT INTO horarios (id_usuario, dia_semana, hora_inicio, hora_fin) VALUES (%s, %s, %s, %s)",
                   (id_usuario, dia_semana, hora_inicio, hora_fin))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def eliminar_horario(id_horario, id_usuario):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM horarios WHERE id_horario=%s AND id_usuario=%s", (id_horario, id_usuario))
    conn.commit()
    cursor.close()
    conn.close()
    return True

# ===== RECORDATORIOS =====

def crear_recordatorio_vencimiento(id_usuario, titulo_tarea, fecha_limite):
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    f = datetime.strptime(str(fecha_limite)[:10], "%Y-%m-%d")
    d1 = f - timedelta(days=1)
    d2 = f - timedelta(hours=12)
    cursor.execute("INSERT INTO recordatorios (id_usuario, mensaje, fecha_programada) VALUES (%s, %s, %s)",
                   (id_usuario, f"Recordatorio: La tarea '{titulo_tarea}' vence Manana", d1))
    cursor.execute("INSERT INTO recordatorios (id_usuario, mensaje, fecha_programada) VALUES (%s, %s, %s)",
                   (id_usuario, f"URGENTE: La tarea '{titulo_tarea}' vence en 12 horas", d2))
    conn.commit()
    cursor.close()
    conn.close()

def listar_recordatorios(id_usuario):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""SELECT * FROM recordatorios
                      WHERE id_usuario = %s AND fecha_programada <= NOW()
                      ORDER BY fecha_programada DESC""", (id_usuario,))
    r = cursor.fetchall()
    cursor.close()
    conn.close()
    return r

def recordatorios_no_enviados():
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recordatorios WHERE enviado = 0 AND fecha_programada <= NOW()")
    r = cursor.fetchall()
    cursor.close()
    conn.close()
    return r

def marcar_recordatorio_enviado(id_recordatorio):
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    cursor.execute("UPDATE recordatorios SET enviado = 1 WHERE id_recordatorio = %s", (id_recordatorio,))
    conn.commit()
    cursor.close()
    conn.close()

# ===== RECOMENDACIONES =====

def guardar_recomendacion(id_usuario, contenido):
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    cursor.execute("INSERT INTO recomendaciones (id_usuario, contenido) VALUES (%s, %s)", (id_usuario, contenido))
    conn.commit()
    cursor.close()
    conn.close()

def listar_recomendaciones(id_usuario):
    conn = conectar()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recomendaciones WHERE id_usuario = %s ORDER BY fecha DESC", (id_usuario,))
    r = cursor.fetchall()
    cursor.close()
    conn.close()
    return r

# ===== ESTADISTICAS =====

def obtener_estadisticas(id_usuario):
    conn = conectar()
    if not conn:
        return {}
    cursor = conn.cursor(dictionary=True)
    stats = {}

    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s", (id_usuario,))
    stats["total_tareas"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'pendiente'", (id_usuario,))
    stats["pendientes"] = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'completada'", (id_usuario,))
    stats["completadas"] = cursor.fetchone()["total"]

    cursor.execute("""SELECT COUNT(*) as total FROM tareas
                      WHERE id_usuario = %s AND fecha_limite < CURDATE() AND estado = 'pendiente'""", (id_usuario,))
    stats["vencidas"] = cursor.fetchone()["total"]

    cursor.execute("""SELECT m.nombre, AVG(n.calificacion) as promedio
                      FROM notas n JOIN materias m ON n.id_materia = m.id_materia
                      WHERE n.id_usuario = %s GROUP BY m.nombre""", (id_usuario,))
    stats["promedios_materias"] = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM materias WHERE id_usuario = %s", (id_usuario,))
    stats["total_materias"] = cursor.fetchone()["total"]

    cursor.close()
    conn.close()
    return stats
