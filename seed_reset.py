"""
Reset usuario 1 y cargar datos de ejemplo
"""
import hashlib
from datetime import datetime, timedelta
from conexion import conectar

hoy = datetime.now().date()

conn = conectar()
cursor = conn.cursor()

# Limpiar datos existentes del usuario 1
cursor.execute("DELETE FROM recomendaciones WHERE id_usuario = 1")
cursor.execute("DELETE FROM recordatorios WHERE id_usuario = 1")
cursor.execute("DELETE FROM notas WHERE id_usuario = 1")
cursor.execute("DELETE FROM horarios WHERE id_usuario = 1")
cursor.execute("DELETE FROM tareas WHERE id_usuario = 1")
cursor.execute("DELETE FROM materias WHERE id_usuario = 1")
cursor.execute("DELETE FROM usuarios WHERE id_usuario = 1")

# Crear usuario
h = hashlib.sha256("123456".encode()).hexdigest()
cursor.execute("INSERT INTO usuarios (id_usuario, nombre, email, contraseña) VALUES (%s, %s, %s, %s)",
               (1, "Estudiante", "estudiante@correo.com", h))

# Materias
mats = [
    ("Matematicas", "Carlos Mendez", "#e74c3c"),
    ("Programacion", "Ana Lopez", "#2ecc71"),
    ("Base de Datos", "Pedro Ramirez", "#3498db"),
    ("Ingles", "Sofia Torres", "#f39c12"),
    ("Redes", "Marco Diaz", "#9b59b6"),
]
for i, (nom, prof, col) in enumerate(mats, 1):
    cursor.execute("INSERT INTO materias (id_materia, id_usuario, nombre, profesor, color) VALUES (%s, %s, %s, %s, %s)",
                   (i, 1, nom, prof, col))

# Tareas
tareas = [
    ("Taller de integrales", "Resolver ejercicios 1-10 del capitulo 5", str(hoy + timedelta(days=2)), "alta", 120),
    ("Proyecto final POO", "Avance del proyecto de Java", str(hoy + timedelta(days=5)), "alta", 180),
    ("Examen de SQL", "Estudiar joins y subconsultas", str(hoy + timedelta(days=1)), "alta", 90),
    ("Ensayo de Ingles", "Escribir 2 paginas sobre tecnologia", str(hoy + timedelta(days=7)), "media", 60),
    ("Ejercicios de redes", "Capas OSI y TCP/IP", str(hoy + timedelta(days=3)), "media", 45),
    ("Lectura base de datos", "Capitulo 4: Normalizacion", str(hoy + timedelta(days=10)), "baja", 30),
    ("Taller de matrices", "Multiplicacion y determinantes", str(hoy + timedelta(days=4)), "media", 90),
    ("Preparacion exposicion", "Diapositivas del proyecto", str(hoy + timedelta(days=6)), "baja", 60),
]
for tit, desc, fecha, dif, tiempo in tareas:
    cursor.execute("INSERT INTO tareas (id_usuario, titulo, descripcion, fecha_limite, dificultad, tiempo_estimado) VALUES (%s, %s, %s, %s, %s, %s)",
                   (1, tit, desc, fecha, dif, tiempo))

# Horarios
horarios = [
    ("lunes", "08:00", "10:00"), ("lunes", "14:00", "16:00"),
    ("martes", "09:00", "11:00"), ("martes", "15:00", "17:00"),
    ("miercoles", "08:00", "10:00"), ("miercoles", "14:00", "16:00"),
    ("jueves", "10:00", "12:00"), ("jueves", "15:00", "18:00"),
    ("viernes", "08:00", "12:00"), ("sabado", "09:00", "13:00"),
]
for dia, inicio, fin in horarios:
    cursor.execute("INSERT INTO horarios (id_usuario, dia_semana, hora_inicio, hora_fin) VALUES (%s, %s, %s, %s)",
                   (1, dia, inicio, fin))

# Notas
notas = [(1, 4.5, "Parcial 1"), (2, 3.8, "Taller"), (3, 4.2, "Proyecto modulo 1"),
         (4, 4.0, "Examen parcial"), (5, 4.8, "Speaking test")]
for id_mat, cal, desc in notas:
    cursor.execute("INSERT INTO notas (id_usuario, id_materia, calificacion, descripcion) VALUES (%s, %s, %s, %s)",
                   (1, id_mat, cal, desc))

conn.commit()
cursor.close()
conn.close()
print("USUARIO Y DATOS DE EJEMPLO CARGADOS EXITOSAMENTE")
print("Email: estudiante@correo.com / Pass: 123456")
