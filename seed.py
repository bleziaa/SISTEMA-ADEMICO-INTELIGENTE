"""
Script para poblar la BD con datos de ejemplo
Ejecutar: python seed.py
"""
from modelos import crear_materia, crear_tarea, crear_nota, crear_horario
from conexion import conectar
import hashlib

ID = 1  # id del usuario ya creado

# ===== MATERIAS =====
materias = [
    ("Matematicas", "Carlos Mendez", "#e74c3c"),
    ("Programacion", "Ana Lopez", "#2ecc71"),
    ("Base de Datos", "Pedro Ramirez", "#3498db"),
    ("Ingles", "Sofia Torres", "#f39c12"),
    ("Redes", "Marco Diaz", "#9b59b6"),
]
for nombre, prof, color in materias:
    crear_materia(ID, nombre, prof, color)
print("5 materias creadas")

# ===== TAREAS =====
from datetime import datetime, timedelta
hoy = datetime.now().date()

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
for titulo, desc, fecha, dif, tiempo in tareas:
    crear_tarea(ID, titulo, desc, fecha, dif, tiempo)
print("8 tareas creadas")

# ===== HORARIOS =====
horarios = [
    ("lunes", "08:00", "10:00"),
    ("lunes", "14:00", "16:00"),
    ("martes", "09:00", "11:00"),
    ("martes", "15:00", "17:00"),
    ("miercoles", "08:00", "10:00"),
    ("miercoles", "14:00", "16:00"),
    ("jueves", "10:00", "12:00"),
    ("jueves", "15:00", "18:00"),
    ("viernes", "08:00", "12:00"),
    ("sabado", "09:00", "13:00"),
]
for dia, inicio, fin in horarios:
    crear_horario(ID, dia, inicio, fin)
print("10 horarios creados")

# ===== NOTAS =====
notas = [
    (1, 4.5, "Parcial 1"),
    (1, 3.8, "Taller"),
    (2, 4.2, "Proyecto modulo 1"),
    (2, 3.5, "Quiz"),
    (3, 4.0, "Examen parcial"),
    (4, 4.8, "Speaking test"),
    (5, 3.2, "Taller redes"),
]
# Obtener ids reales de materias
conn = conectar()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT id_materia FROM materias WHERE id_usuario = %s ORDER BY id_materia", (ID,))
mat_ids = [r["id_materia"] for r in cursor.fetchall()]
cursor.close()
conn.close()

for i, (_, calif, desc) in enumerate(notas):
    if i < len(mat_ids):
        crear_nota(ID, mat_ids[i], calif, desc)
print(f"{len(notas)} notas creadas")

print("\n✅ DATOS DE EJEMPLO CARGADOS EXITOSAMENTE")
print("   Inicia sesion con: estudiante@correo.com / 123456")
