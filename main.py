from usuarios import crear_usuario
from tareas import crear_tarea
from conexion import conectar
from ia import generar_horario


def ver_datos():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios")
    print("\n👤 USUARIOS:")
    for u in cursor.fetchall():
        print(u)

    cursor.execute("SELECT * FROM tareas")
    print("\n📌 TAREAS:")
    for t in cursor.fetchall():
        print(t)

    cursor.close()
    conn.close()


# ===== EJECUCIÓN CONTROLADA =====
if __name__ == "__main__":

    print("\n--- DATOS ACTUALES ---")
    ver_datos()

    opcion = input("\n¿Generar horario con IA? (s/n): ")

    if opcion.lower() == "s":
        print("\n--- GENERANDO HORARIO ---")
        generar_horario(1)
    else:
        print("\n⏸️ IA no ejecutada")