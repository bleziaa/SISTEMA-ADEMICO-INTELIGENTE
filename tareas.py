from conexion import conectar

def crear_tarea(id_usuario, titulo, dificultad, tiempo):
    conn = conectar()
    cursor = conn.cursor()

    sql = """
    INSERT INTO tareas (id_usuario, titulo, dificultad, tiempo_estimado)
    VALUES (%s, %s, %s, %s)
    """

    valores = (id_usuario, titulo, dificultad, tiempo)

    cursor.execute(sql, valores)
    conn.commit()

    print("✅ Tarea creada")

    cursor.close()
    conn.close()