import mysql.connector
import os

conn = mysql.connector.connect(
    host=os.environ['MYSQLHOST'],
    user=os.environ['MYSQLUSER'],
    password=os.environ['MYSQLPASSWORD'],
    database=os.environ['MYSQLDATABASE'],
    port=3306
)
cursor = conn.cursor(dictionary=True)

# List existing users
cursor.execute("SELECT id_usuario, nombre, email FROM usuarios LIMIT 5")
usuarios = cursor.fetchall()
print("Usuarios existentes:")
for u in usuarios:
    print(f"  {u['id_usuario']}: {u['nombre']} - {u['email']}")

# Use first user or create demo user
if not usuarios:
    import bcrypt
    pwd = bcrypt.hashpw("demo1234".encode(), bcrypt.gensalt()).decode()
    cursor.execute("INSERT INTO usuarios (nombre, email, contrasena) VALUES (%s, %s, %s)",
                   ("Estudiante Demo", "demo@academia.com", pwd))
    conn.commit()
    user_id = cursor.lastrowid
    print(f"Creado usuario demo (id={user_id})")
else:
    user_id = usuarios[0]['id_usuario']
    print(f"Usando usuario id={user_id}")

# Add subjects if empty
cursor.execute("SELECT COUNT(*) as c FROM materias WHERE id_usuario=%s", (user_id,))
if cursor.fetchone()['c'] == 0:
    materias = [
        ("Calculo Diferencial", "Dr. Pedro Martinez", "#3B82F6"),
        ("Programacion Orientada a Objetos", "Ing. Maria Lopez", "#10B981"),
        ("Bases de Datos", "Prof. Carlos Sanchez", "#F59E0B"),
        ("Estructuras de Datos", "Ing. Ana Torres", "#EF4444"),
        ("Ingles Tecnico", "Lic. Laura Jimenez", "#8B5CF6"),
        ("Ingenieria de Software", "Ing. Roberto Gomez", "#EC4899"),
    ]
    for m in materias:
        cursor.execute("INSERT INTO materias (id_usuario, nombre, profesor, color) VALUES (%s, %s, %s, %s)",
                       (user_id, m[0], m[1], m[2]))
    conn.commit()
    print(f"Materias creadas: {len(materias)}")

# Get subject IDs
cursor.execute("SELECT id_materia, nombre FROM materias WHERE id_usuario=%s", (user_id,))
materias = {m['nombre']: m['id_materia'] for m in cursor.fetchall()}

# Add tasks if empty
cursor.execute("SELECT COUNT(*) as c FROM tareas WHERE id_usuario=%s", (user_id,))
if cursor.fetchone()['c'] == 0:
    from datetime import datetime, timedelta
    hoy = datetime.now().date()
    tareas = [
        ("Ejercicios de limites", "Resolver ejercicios pares del capitulo 3", str(hoy + timedelta(days=2)), "Calculo Diferencial", "alta", 120),
        ("Taller de herencia", "Completar taller de clases y herencia en Java", str(hoy + timedelta(days=5)), "Programacion Orientada a Objetos", "media", 90),
        ("Diagrama ER", "Disenar diagrama entidad-relacion del proyecto", str(hoy + timedelta(days=1)), "Bases de Datos", "alta", 60),
        ("Implementar lista enlazada", "Crear lista enlazada simple en C++", str(hoy + timedelta(days=7)), "Estructuras de Datos", "media", 120),
        ("Traduccion del articulo", "Traducir resumen del articulo cientifico", str(hoy + timedelta(days=3)), "Ingles Tecnico", "baja", 45),
        ("Consultas SQL", "Escribir 10 consultas SQL avanzadas", str(hoy + timedelta(days=4)), "Bases de Datos", "alta", 90),
        ("Ejercicios de derivadas", "Practicar regla de la cadena", str(hoy + timedelta(days=6)), "Calculo Diferencial", "media", 60),
        # Ingenieria de Software tasks
        ("Analisis de Requisitos", "Documento de especificacion de requisitos para sistema de gestion de biblioteca", str(hoy + timedelta(days=3)), "Ingenieria de Software", "alta", 180),
        ("Diseno de Arquitectura", "Crear diagrama de arquitectura MVC para aplicacion web", str(hoy + timedelta(days=5)), "Ingenieria de Software", "alta", 150),
        ("Modelado UML", "Disenar diagrama de clases UML para sistema de reservas", str(hoy + timedelta(days=7)), "Ingenieria de Software", "media", 120),
        ("Testing y QA", "Plan de pruebas unitarias y de integracion", str(hoy + timedelta(days=9)), "Ingenieria de Software", "alta", 150),
        ("Documentacion Tecnica", "Documentacion tecnica completa del proyecto", str(hoy + timedelta(days=11)), "Ingenieria de Software", "media", 120),
        ("Gestion de Proyectos", "Crear cronograma y matriz de riesgos", str(hoy + timedelta(days=8)), "Ingenieria de Software", "media", 90),
        ("Patrones de Diseno", "Implementar patron Singleton y Factory en codigo", str(hoy + timedelta(days=12)), "Ingenieria de Software", "alta", 180),
        ("Code Review", "Revisar y documentar mejoras de codigo", str(hoy + timedelta(days=14)), "Ingenieria de Software", "baja", 60),
    ]
    for t in tareas:
        mid = materias.get(t[3])
        cursor.execute("""INSERT INTO tareas (id_usuario, id_materia, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                       (user_id, mid, t[0], t[1], t[2], t[4], t[5]))
    conn.commit()
    print(f"Tareas creadas: {len(tareas)}")

# Add grades
cursor.execute("SELECT COUNT(*) as c FROM notas WHERE id_usuario=%s", (user_id,))
if cursor.fetchone()['c'] == 0:
    notas_data = [
        ("Calculo Diferencial", 4.5),
        ("Programacion Orientada a Objetos", 4.8),
        ("Bases de Datos", 4.2),
        ("Estructuras de Datos", 3.8),
        ("Ingles Tecnico", 4.0),
        ("Ingenieria de Software", 4.6),
    ]
    for n in notas_data:
        mid = materias.get(n[0])
        if mid:
            cursor.execute("INSERT INTO notas (id_usuario, id_materia, calificacion, descripcion) VALUES (%s, %s, %s, %s)",
                           (user_id, mid, n[1], f"Nota final {n[0]}"))
    conn.commit()
    print(f"Notas creadas: {len(notas_data)}")

# Add schedules
cursor.execute("SELECT COUNT(*) as c FROM horarios WHERE id_usuario=%s", (user_id,))
if cursor.fetchone()['c'] == 0:
    horarios_data = [
        ("lunes", "07:00", "09:00", "clase"),
        ("lunes", "14:00", "16:00", "clase"),
        ("martes", "08:00", "10:00", "clase"),
        ("martes", "15:00", "17:00", "libre"),
        ("miercoles", "07:00", "09:00", "clase"),
        ("miercoles", "10:00", "12:00", "clase"),
        ("miercoles", "13:00", "15:00", "libre"),
        ("jueves", "09:00", "11:00", "clase"),
        ("jueves", "14:00", "16:00", "libre"),
        ("viernes", "07:00", "12:00", "clase"),
        ("viernes", "13:00", "15:00", "clase"),
        ("sabado", "09:00", "11:00", "clase"),
    ]
    for h in horarios_data:
        cursor.execute("INSERT INTO horarios (id_usuario, dia_semana, hora_inicio, hora_fin, tipo) VALUES (%s, %s, %s, %s, %s)",
                       (user_id, h[0], h[1], h[2], h[3]))
    conn.commit()
    print(f"Horarios creados: {len(horarios_data)}")

cursor.close()
conn.close()
print("\nSeed completado exitosamente!")
