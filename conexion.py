import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def conectar():
    try:
        conexion = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASS", "TADOMAKI"),
            database=os.getenv("DB_NAME", "agenda_inteligente")
        )
        return conexion
    except Error as e:
        print(f"Error de conexion: {e}")
        return None
