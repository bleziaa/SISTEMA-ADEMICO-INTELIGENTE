import mysql.connector

def conectar():
    conexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password="TADOMAKI",  #
        database="agenda_inteligente"
    )
    return conexion