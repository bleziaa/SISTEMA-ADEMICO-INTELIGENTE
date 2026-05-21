"""
SISTEMA - ASISTENTE ACADEMICO INTELIGENTE
Universidad de Cartagena
Analisis y Desarrollo de Software

Ejecutar con: python app.py
"""

from app import app

if __name__ == "__main__":
    print("🎓 Asistente Academico Inteligente")
    print("📌 Abrir en: http://localhost:5000")
    app.run(debug=True, port=5000)
