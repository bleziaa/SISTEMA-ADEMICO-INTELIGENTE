from conexion import conectar
from datetime import datetime, timedelta
import secrets
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _enviar_correo(destinatario, asunto, cuerpo_html, enlace_fallback=None):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)
    smtp_from_name = os.getenv("SMTP_FROM_NAME", "AcademIA")

    if not smtp_host or not smtp_user or not smtp_pass:
        logger.warning("SMTP no configurado")
        if enlace_fallback:
            logger.info("=== ENLACE DE RECUPERACION (copia y pega en el navegador) ===")
            logger.info(enlace_fallback)
            logger.info("=== =========================== ===")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{smtp_from_name} <{smtp_from}>"
        msg["To"] = destinatario
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [destinatario], msg.as_string())
        logger.info("Correo enviado a %s", destinatario)
        return True
    except Exception as e:
        logger.error("Error al enviar correo a %s: %s", destinatario, e)
        if enlace_fallback:
            logger.info("=== ENLACE DE RECUPERACION (fallback por error SMTP) ===")
            logger.info(enlace_fallback)
            logger.info("=== =========================== ===")
        return False

def _registrar_auditoria(id_usuario, accion, detalle=None, direccion_ip=None):
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO auditoria (id_usuario, accion, detalle, direccion_ip) VALUES (%s, %s, %s, %s)",
        (id_usuario, accion, detalle, direccion_ip),
    )
    conn.commit()
    cursor.close()
    conn.close()

def hash_contrasena(contrasena):
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verificar_contrasena(contrasena, hash_almacenado):
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_almacenado.encode("utf-8"))
    except ValueError:
        return False

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
    h = hash_contrasena(contrasena)
    cursor.execute(
        "INSERT INTO usuarios (nombre, email, contrasena) VALUES (%s, %s, %s)",
        (nombre, email, h),
    )
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

def obtener_usuario_por_id(id_usuario):
    conn = conectar()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (id_usuario,))
    u = cursor.fetchone()
    cursor.close()
    conn.close()
    return u

def actualizar_contrasena(id_usuario, nueva_contrasena):
    conn = conectar()
    if not conn:
        return False
    cursor = conn.cursor()
    h = hash_contrasena(nueva_contrasena)
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
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    u = cursor.fetchone()
    cursor.close()
    conn.close()
    if u and verificar_contrasena(contrasena, u["contrasena"]):
        return u
    return None

def solicitar_restablecimiento(email, direccion_ip=None):
    conn = conectar()
    if not conn:
        return False, None
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
    usuario = cursor.fetchone()
    cursor.close()
    conn.close()

    if not usuario:
        _registrar_auditoria(None, "INTENTO_RECUPERACION", f"Email no registrado: {email}", direccion_ip)
        return True, None

    _registrar_auditoria(usuario["id_usuario"], "SOLICITUD_RECUPERACION", direccion_ip=direccion_ip)

    token = secrets.token_urlsafe(48)
    expiracion = datetime.now() + timedelta(minutes=15)

    conn = conectar()
    if not conn:
        return False, None
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO password_reset_tokens (id_usuario, token, fecha_expiracion) VALUES (%s, %s, %s)",
        (usuario["id_usuario"], token, expiracion),
    )
    conn.commit()
    cursor.close()
    conn.close()

    app_url = os.getenv("APP_URL", "http://localhost:5000")
    enlace = f"{app_url}/reset-password?token={token}"
    asunto = "Recuperacion de contrasena - AcademIA"
    cuerpo_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #06b6d4;">AcademIA</h1>
            <h2>Recuperacion de contrasena</h2>
        </div>
        <p>Hola <strong>{usuario['nombre']}</strong>,</p>
        <p>Recibimos una solicitud para restablecer tu contrasena. Haz clic en el siguiente enlace para crear una nueva:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{enlace}"
               style="background-color: #06b6d4; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">
                Restablecer contrasena
            </a>
        </div>
        <p>Este enlace expira en <strong>15 minutos</strong>.</p>
        <p>Si no solicitaste este cambio, ignora este correo.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #888; font-size: 12px;">AcademIA - Tu asistente academico inteligente</p>
    </div>
    """
    _enviar_correo(usuario["email"], asunto, cuerpo_html, enlace_fallback=enlace)
    return True, enlace

def validar_token_restablecimiento(token):
    conn = conectar()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM password_reset_tokens WHERE token = %s AND usado = 0 AND fecha_expiracion > NOW()",
        (token,),
    )
    t = cursor.fetchone()
    cursor.close()
    conn.close()
    return t

def restablecer_contrasena(token, nueva_contrasena, direccion_ip=None):
    t = validar_token_restablecimiento(token)
    if not t:
        return False, "Token invalido o expirado"

    id_usuario = t["id_usuario"]
    if not actualizar_contrasena(id_usuario, nueva_contrasena):
        return False, "Error al actualizar la contrasena"

    conn = conectar()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE password_reset_tokens SET usado = 1 WHERE id_token = %s", (t["id_token"],))
        conn.commit()
        cursor.close()
        conn.close()

    _registrar_auditoria(id_usuario, "RESTABLECIMIENTO_EXITOSO", direccion_ip=direccion_ip)
    return True, "Contrasena actualizada exitosamente"

def limpiar_tokens_expirados():
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor()
    cursor.execute("DELETE FROM password_reset_tokens WHERE fecha_expiracion <= NOW() AND usado = 0")
    conn.commit()
    cursor.close()
    conn.close()

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

# ===== SEED DATA =====

def seed_sample_data():
    conn = conectar()
    if not conn:
        return
    cursor = conn.cursor(dictionary=True)
    from datetime import datetime, timedelta
    cursor.execute("SELECT id_usuario FROM usuarios LIMIT 1")
    user = cursor.fetchone()
    if not user:
        import bcrypt
        pwd = bcrypt.hashpw("demo1234".encode(), bcrypt.gensalt()).decode()
        cursor.execute("INSERT INTO usuarios (nombre, email, contrasena) VALUES (%s, %s, %s)",
                       ("Estudiante Demo", "demo@academia.com", pwd))
        conn.commit()
        user_id = cursor.lastrowid
        logger.info("Seed: usuario demo creado (demo@academia.com / demo1234)")
    else:
        user_id = user["id_usuario"]
    cursor.execute("SELECT COUNT(*) as c FROM materias WHERE id_usuario=%s", (user_id,))
    if cursor.fetchone()["c"] == 0:
        materias = [
            ("Calculo Diferencial", "Dr. Pedro Martinez", "#3B82F6"),
            ("Programacion Orientada a Objetos", "Ing. Maria Lopez", "#10B981"),
            ("Bases de Datos", "Prof. Carlos Sanchez", "#F59E0B"),
            ("Estructuras de Datos", "Ing. Ana Torres", "#EF4444"),
            ("Ingles Tecnico", "Lic. Laura Jimenez", "#8B5CF6"),
        ]
        for m in materias:
            cursor.execute("INSERT INTO materias (id_usuario, nombre, profesor, color) VALUES (%s, %s, %s, %s)", (user_id, *m))
        conn.commit()
        logger.info("Seed: 5 materias creadas")
    cursor.execute("SELECT id_materia, nombre FROM materias WHERE id_usuario=%s", (user_id,))
    mids = {r["nombre"]: r["id_materia"] for r in cursor.fetchall()}
    cursor.execute("SELECT COUNT(*) as c FROM tareas WHERE id_usuario=%s", (user_id,))
    if cursor.fetchone()["c"] == 0:
        hoy = datetime.now().date()
        tareas = [
            ("Ejercicios de limites", "Resolver ejercicios pares del capitulo 3", str(hoy + timedelta(days=2)), "Calculo Diferencial", "alta", 120),
            ("Taller de herencia", "Completar taller de clases y herencia en Java", str(hoy + timedelta(days=5)), "Programacion Orientada a Objetos", "media", 90),
            ("Diagrama ER", "Disenar diagrama entidad-relacion del proyecto", str(hoy + timedelta(days=1)), "Bases de Datos", "alta", 60),
            ("Implementar lista enlazada", "Crear lista enlazada simple en C++", str(hoy + timedelta(days=7)), "Estructuras de Datos", "media", 120),
            ("Traduccion del articulo", "Traducir resumen del articulo cientifico", str(hoy + timedelta(days=3)), "Ingles Tecnico", "baja", 45),
        ]
        for t in tareas:
            mid = mids.get(t[3])
            cursor.execute("INSERT INTO tareas (id_usuario, id_materia, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado) VALUES (%s,%s,%s,%s,%s,%s,%s)", (user_id, mid, t[0], t[1], t[2], t[4], t[5]))
        conn.commit()
        logger.info("Seed: 5 tareas creadas")
    cursor.execute("SELECT COUNT(*) as c FROM notas WHERE id_usuario=%s", (user_id,))
    if cursor.fetchone()["c"] == 0:
        for n in [("Calculo Diferencial", 4.5), ("Programacion Orientada a Objetos", 4.8), ("Bases de Datos", 4.2), ("Estructuras de Datos", 3.8), ("Ingles Tecnico", 4.0)]:
            mid = mids.get(n[0])
            if mid:
                cursor.execute("INSERT INTO notas (id_usuario, id_materia, calificacion) VALUES (%s, %s, %s)", (user_id, mid, n[1]))
        conn.commit()
        logger.info("Seed: 5 notas creadas")
    cursor.execute("SELECT COUNT(*) as c FROM horarios WHERE id_usuario=%s", (user_id,))
    if cursor.fetchone()["c"] == 0:
        for h in [("lunes","07:00","09:00"),("lunes","14:00","16:00"),("martes","08:00","10:00"),("martes","15:00","17:00"),("miercoles","07:00","09:00"),("miercoles","13:00","15:00"),("jueves","09:00","11:00"),("jueves","14:00","16:00"),("viernes","07:00","12:00")]:
            cursor.execute("INSERT INTO horarios (id_usuario, dia_semana, hora_inicio, hora_fin, tipo) VALUES (%s, %s, %s, %s, 'clase')", (user_id, h[0], h[1], h[2]))
        conn.commit()
        logger.info("Seed: 9 horarios creados")
    cursor.close()
    conn.close()
    logger.info("Seed: muestra de datos completada")
