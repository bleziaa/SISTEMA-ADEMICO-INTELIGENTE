import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("❌ No se encontró la API KEY")

genai.configure(api_key=API_KEY)

modelo = genai.GenerativeModel("gemini-2.5-flash")

def generar_horario(id_usuario):
    conn = conectar()
    cursor = conn.cursor()

    # Obtener tareas
    cursor.execute("""
        SELECT titulo, dificultad, tiempo_estimado 
        FROM tareas 
        WHERE id_usuario = %s AND estado = 'pendiente'
    """, (id_usuario,))
    tareas = cursor.fetchall()

    # Obtener horarios
    cursor.execute("""
        SELECT dia_semana, hora_inicio, hora_fin 
        FROM horarios 
        WHERE id_usuario = %s
    """, (id_usuario,))
    horarios = cursor.fetchall()

    # VALIDACIÓN
    if not tareas or not horarios:
        print("⚠️ No hay suficientes datos para generar horario")
        cursor.close()
        conn.close()
        return

    # Evitar duplicados de recomendaciones
    cursor.execute("""
        SELECT * FROM recomendaciones 
        WHERE id_usuario = %s
    """, (id_usuario,))
    if cursor.fetchone():
        print("📌 Ya existe un horario generado")
        cursor.close()
        conn.close()
        return

    # Prompt
    prompt = f"""
    Organiza estas tareas en los horarios disponibles:

    Tareas:
    {tareas}

    Horarios:
    {horarios}

    Reglas:
    - Prioriza tareas difíciles
    - No sobrecargar
    """

    # 🔁 INTENTOS AUTOMÁTICOS (manejo de errores)
    intentos = 3
    for i in range(intentos):
        try:
            respuesta = modelo.generate_content(prompt)
            resultado = respuesta.text
            break
        except Exception as e:
            print(f"⚠️ Error intento {i+1}: {e}")
            time.sleep(5)
    else:
        print("❌ No se pudo generar el horario por la IA")
        cursor.close()
        conn.close()
        return

    # Guardar en BD
    cursor.execute("""
        INSERT INTO recomendaciones (id_usuario, contenido)
        VALUES (%s, %s)
    """, (id_usuario, resultado))

    conn.commit()

    print("\n🧠 HORARIO GENERADO:\n")
    print(resultado)

    cursor.close()
    conn.close()