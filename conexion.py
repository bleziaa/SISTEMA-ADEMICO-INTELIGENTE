import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def conectar():
    try:
        conexion = mysql.connector.connect(
            host=os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "localhost",
            user=os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root",
            password=os.getenv("DB_PASS") or os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_ROOT_PASSWORD") or "TADOMAKI",
            database=os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE") or "agenda_inteligente",
            port=os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or 3306
        )
        return conexion
    except Error as e:
        print(f"Error de conexion: {e}")
        return None
