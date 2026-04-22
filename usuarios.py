from conexion import conectar

def crear_usuario(nombre, email):
    conn = conectar()
    cursor = conn.cursor()

    sql = "INSERT INTO usuarios (nombre, email) VALUES (%s, %s)"
    valores = (nombre, email)

    cursor.execute(sql, valores)
    conn.commit()

    print("✅ Usuario creado")

    cursor.close()
    conn.close()
  