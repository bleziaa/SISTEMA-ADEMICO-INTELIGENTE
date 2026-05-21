import os
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from conexion import conectar

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
usa_ia = False
modelo = None

if API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        modelo = genai.GenerativeModel("gemini-2.0-flash")
        usa_ia = True
    except Exception:
        pass

def generar_horario(id_usuario):
    conn = conectar()
    if not conn:
        return None, "Error de conexion a la BD"
    cursor = conn.cursor()

    cursor.execute("""
        SELECT titulo, dificultad, tiempo_estimado, fecha_limite
        FROM tareas
        WHERE id_usuario = %s AND estado = 'pendiente'
        ORDER BY fecha_limite ASC
    """, (id_usuario,))
    tareas = cursor.fetchall()

    cursor.execute("""
        SELECT dia_semana, hora_inicio, hora_fin
        FROM horarios
        WHERE id_usuario = %s
        ORDER BY FIELD(dia_semana,'lunes','martes','miercoles','jueves','viernes','sabado','domingo'), hora_inicio
    """, (id_usuario,))
    horarios = cursor.fetchall()
    cursor.close()
    conn.close()

    if not tareas:
        return None, "No hay tareas pendientes para generar horario"
    if not horarios:
        return None, "No hay horarios registrados. Registra tu disponibilidad primero"

    if usa_ia:
        resultado = _generar_con_ia(tareas, horarios)
        if resultado:
            return resultado, None

    return _generar_local(tareas, horarios), None

def generar_recomendacion(id_usuario, estadisticas):
    if usa_ia:
        resultado = _recomendacion_con_ia(estadisticas)
        if resultado:
            return resultado, None
    return _recomendacion_local(estadisticas), None

# ===== FALLBACK LOCAL =====

def _generar_local(tareas, horarios):
    hoy = datetime.now().date()
    dias_espanol = {"lunes": "Lunes", "martes": "Martes", "miercoles": "Miercoles",
                    "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sabado", "domingo": "Domingo"}
    orden_dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

    tareas_con_prioridad = []
    for t in tareas:
        titulo, dificultad, tiempo, fecha_lim = t[0], t[1], t[2], str(t[3])[:10]
        df = datetime.strptime(fecha_lim, "%Y-%m-%d").date()
        dias_rest = (df - hoy).days
        pdif = {"baja": 1, "media": 2, "alta": 3}.get(dificultad, 2)
        prioridad = pdif * 10 + max(0, 14 - dias_rest)
        tareas_con_prioridad.append((prioridad, titulo, dificultad, tiempo, fecha_lim))
    tareas_con_prioridad.sort(reverse=True)

    horarios_por_dia = {d: [] for d in orden_dias}
    for h in horarios:
        dia = h[0]
        raw_inicio = h[1]
        raw_fin = h[2]
        if isinstance(raw_inicio, timedelta):
            inicio = (datetime.min + raw_inicio).strftime("%H:%M")
        else:
            inicio = (str(raw_inicio)[:5] if raw_inicio else "00:00")
            if len(inicio) == 4:
                inicio = "0" + inicio
        if isinstance(raw_fin, timedelta):
            fin = (datetime.min + raw_fin).strftime("%H:%M")
        else:
            fin = (str(raw_fin)[:5] if raw_fin else "00:00")
            if len(fin) == 4:
                fin = "0" + fin
        hi = int(inicio[:2]) * 60 + int(inicio[3:])
        hf = int(fin[:2]) * 60 + int(fin[3:])
        horarios_por_dia[dia].append((hi, hf, inicio, fin))

    resultado = ["HORARIO DE ESTUDIO SEMANAL\n"]
    resultado.append("=" * 50)
    resultado.append(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    resultado.append(f"Tareas pendientes: {len(tareas)}")
    resultado.append("=" * 50)

    tareas_asignadas = 0
    for dia in orden_dias:
        slots = horarios_por_dia[dia]
        if not slots:
            continue
        resultado.append(f"\n--- {dias_espanol[dia]} ---")
        for hi, hf, inicio, fin in slots:
            disponibles = hf - hi
            if disponibles <= 0:
                continue
            bloque = min(disponibles, 180)
            while bloque >= 30 and tareas_asignadas < len(tareas_con_prioridad):
                _, titulo, dificultad, tiempo, fecha_lim = tareas_con_prioridad[tareas_asignadas]
                tiempo_asignado = min(tiempo, bloque)
                resultado.append(f"  {inicio}-{_sumar_minutos(inicio, tiempo_asignado)} | {titulo} ({dificultad}, {tiempo_asignado}min) - Vence: {fecha_lim}")
                inicio = _sumar_minutos(inicio, tiempo_asignado)
                bloque -= tiempo_asignado
                tareas_asignadas += 1
                if bloque >= 30:
                    resultado.append(f"  {inicio}-{_sumar_minutos(inicio, 10)} | DESCANSO (10min)")
                    inicio = _sumar_minutos(inicio, 10)
                    bloque -= 10

    resultado.append(f"\n{'=' * 50}")
    resultado.append(f"Total tareas asignadas: {tareas_asignadas} de {len(tareas)}")
    resultado.append(f"Tareas sin asignar: {len(tareas) - tareas_asignadas}")
    resultado.append(f"{'=' * 50}")
    resultado.append("\nConsejo: Revisa tu disponibilidad y agrega mas horarios si es necesario.")

    return "\n".join(resultado)

def _recomendacion_local(estadisticas):
    lineas = ["RECOMENDACIONES ACADEMICAS\n"]
    lineas.append("=" * 50)

    total = estadisticas.get("total_tareas", 0)
    completadas = estadisticas.get("completadas", 0)
    pendientes = estadisticas.get("pendientes", 0)
    vencidas = estadisticas.get("vencidas", 0)

    if total > 0:
        pct = completadas / total * 100
        if pct >= 80:
            lineas.append(" Excelente progreso! Sigues asi!")
        elif pct >= 50:
            lineas.append(" Buen avance, pero puedes mejorar.")
        else:
            lineas.append(" Necesitas organizarte mejor.")

    if vencidas > 0:
        lineas.append(f" Tienes {vencidas} tarea(s) vencida(s). Prioriza ponerte al dia.")
    if pendientes > 0:
        lineas.append(f" Aun te quedan {pendientes} tarea(s) pendiente(s).")

    promedios = estadisticas.get("promedios_materias", [])
    if promedios:
        lineas.append("\nPromedios por materia:")
        for p in promedios:
            nombre = p.get("nombre", "?")
            prom = float(p.get("promedio", 0))
            if prom < 3.0:
                lineas.append(f"  {nombre}: {prom:.1f} - Necesitas mejorar")
            elif prom < 4.0:
                lineas.append(f"  {nombre}: {prom:.1f} - Puedes mejorar")
            else:
                lineas.append(f"  {nombre}: {prom:.1f} - Buen rendimiento")

    lineas.append(f"\nConsejos:")
    lineas.append(" 1. Divide tareas grandes en bloques de 30-60 min")
    lineas.append(" 2. Usa la tecnica Pomodoro: 25 min estudio, 5 descanso")
    lineas.append(" 3. Prioriza lo mas urgente y dificil primero")
    lineas.append(" 4. Revisa tu calendario cada manana")

    return "\n".join(lineas)

# ===== GEMINI IA =====

def _generar_con_ia(tareas, horarios):
    prompt = f"""
Eres un asistente academico inteligente. Genera un horario de estudio semanal personalizado.

TAREAS PENDIENTES:
{_formatear_tareas(tareas)}

DISPONIBILIDAD DEL ESTUDIANTE:
{_formatear_horarios(horarios)}

INSTRUCCIONES:
1. Organiza las tareas en los espacios disponibles
2. Prioriza las tareas mas dificiles y con fecha mas cercana
3. Distribuye el tiempo de forma realista
4. No sobrecargues ningun dia
5. Incluye descansos entre tareas
6. Sugiere bloques de estudio de maximo 3 horas
7. Responde en espanol

Formato de salida: tabular por dia con horas y tarea asignada.
"""
    for i in range(3):
        try:
            respuesta = modelo.generate_content(prompt)
            return respuesta.text
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                return None
            if i < 2:
                time.sleep(5)
    return None

def _recomendacion_con_ia(estadisticas):
    prompt = f"""
Eres un asistente academico inteligente. Genera recomendaciones academicas basadas en estos datos:

Tareas completadas: {estadisticas.get('completadas', 0)}
Tareas pendientes: {estadisticas.get('pendientes', 0)}
Tareas vencidas: {estadisticas.get('vencidas', 0)}
Total materias: {estadisticas.get('total_materias', 0)}

Promedios por materia:
{estadisticas.get('promedios_materias', [])}

INSTRUCCIONES:
1. Si hay muchas tareas vencidas, sugiere mejorar la organizacion
2. Si hay bajo rendimiento en alguna materia, recomienda dedicarle mas tiempo
3. Da 3-5 consejos practicos y motivacionales
4. Responde en espanol en tono amigable
"""
    for i in range(3):
        try:
            respuesta = modelo.generate_content(prompt)
            return respuesta.text
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                return None
            if i < 2:
                time.sleep(5)
    return None

def _formatear_tareas(tareas):
    return "\n".join([f"- {t[0]} (Vence: {t[3]}) | Dificultad: {t[1]} | Tiempo: {t[2]}min" for t in tareas])

def _formatear_horarios(horarios):
    def fmt_time(t):
        if isinstance(t, timedelta):
            return (datetime.min + t).strftime("%H:%M")
        s = str(t)[:5]
        return "0" + s if len(s) == 4 else s
    return "\n".join([f"- {h[0].capitalize()}: {fmt_time(h[1])} - {fmt_time(h[2])}" for h in horarios])

def _sumar_minutos(hora_str, minutos):
    h, m = int(hora_str[:2]), int(hora_str[3:])
    total = h * 60 + m + minutos
    return f"{total // 60:02d}:{total % 60:02d}"

def generar_horario_visual(id_usuario):
    conn = conectar()
    if not conn:
        return None, "Error de conexion a la BD"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT titulo, dificultad, tiempo_estimado, fecha_limite
        FROM tareas
        WHERE id_usuario = %s AND estado = 'pendiente'
        ORDER BY fecha_limite ASC
    """, (id_usuario,))
    tareas = cursor.fetchall()
    cursor.execute("""
        SELECT dia_semana, hora_inicio, hora_fin
        FROM horarios
        WHERE id_usuario = %s
        ORDER BY FIELD(dia_semana,'lunes','martes','miercoles','jueves','viernes','sabado','domingo'), hora_inicio
    """, (id_usuario,))
    horarios = cursor.fetchall()
    cursor.close()
    conn.close()
    if not tareas:
        return None, "No hay tareas pendientes"
    if not horarios:
        return None, "No hay horarios registrados"

    hoy = datetime.now().date()
    orden_dias = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
    dias_espanol = {"lunes": "Lunes", "martes": "Martes", "miercoles": "Miercoles",
                    "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sabado", "domingo": "Domingo"}
    tareas_con_prioridad = []
    for t in tareas:
        titulo, dificultad, tiempo, fecha_lim = t[0], t[1], t[2], str(t[3])[:10]
        df = datetime.strptime(fecha_lim, "%Y-%m-%d").date()
        dias_rest = (df - hoy).days
        pdif = {"baja": 1, "media": 2, "alta": 3}.get(dificultad, 2)
        prioridad = pdif * 10 + max(0, 14 - dias_rest)
        tareas_con_prioridad.append((prioridad, titulo, dificultad, tiempo, fecha_lim))
    tareas_con_prioridad.sort(reverse=True)

    horarios_por_dia = {d: [] for d in orden_dias}
    for h in horarios:
        dia = h[0]
        raw_inicio, raw_fin = h[1], h[2]
        if isinstance(raw_inicio, timedelta):
            inicio = (datetime.min + raw_inicio).strftime("%H:%M")
        else:
            inicio = (str(raw_inicio)[:5] if raw_inicio else "00:00")
            if len(inicio) == 4: inicio = "0" + inicio
        if isinstance(raw_fin, timedelta):
            fin = (datetime.min + raw_fin).strftime("%H:%M")
        else:
            fin = (str(raw_fin)[:5] if raw_fin else "00:00")
            if len(fin) == 4: fin = "0" + fin
        hi = int(inicio[:2]) * 60 + int(inicio[3:])
        hf = int(fin[:2]) * 60 + int(fin[3:])
        horarios_por_dia[dia].append((hi, hf, inicio, fin))

    semana = []
    total_asignadas = 0
    tareas_asignadas = 0
    for dia in orden_dias:
        slots = horarios_por_dia[dia]
        entry = {"dia": dias_espanol[dia], "dia_key": dia, "bloques": []}
        if not slots:
            semana.append(entry)
            continue
        for hi, hf, inicio, fin in slots:
            disponibles = hf - hi
            if disponibles <= 0: continue
            bloque = min(disponibles, 180)
            while bloque >= 30 and tareas_asignadas < len(tareas_con_prioridad):
                _, titulo, dificultad, tiempo, fecha_lim = tareas_con_prioridad[tareas_asignadas]
                tiempo_asignado = min(tiempo, bloque)
                entry["bloques"].append({
                    "inicio": inicio,
                    "fin": _sumar_minutos(inicio, tiempo_asignado),
                    "titulo": titulo,
                    "dificultad": dificultad,
                    "tiempo": tiempo_asignado,
                    "fecha_limite": fecha_lim,
                    "es_descanso": False
                })
                inicio = _sumar_minutos(inicio, tiempo_asignado)
                bloque -= tiempo_asignado
                tareas_asignadas += 1
                if bloque >= 30:
                    desc_end = _sumar_minutos(inicio, 10)
                    entry["bloques"].append({
                        "inicio": inicio,
                        "fin": desc_end,
                        "titulo": "DESCANSO",
                        "dificultad": "",
                        "tiempo": 10,
                        "fecha_limite": "",
                        "es_descanso": True
                    })
                    inicio = desc_end
                    bloque -= 10
        semana.append(entry)
    total_asignadas = tareas_asignadas
    return {
        "semana": semana,
        "total_tareas": len(tareas),
        "asignadas": total_asignadas,
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
    }, None


def chat_con_ia(uid, mensaje):
    conn = conectar()
    if not conn:
        return "Error de conexion a la base de datos", None
    cursor = conn.cursor(dictionary=True)

    # Get context
    cursor.execute("SELECT id_materia, nombre FROM materias WHERE id_usuario = %s", (uid,))
    materias = cursor.fetchall()
    cursor.execute("SELECT titulo, fecha_limite, dificultad, estado FROM tareas WHERE id_usuario = %s ORDER BY fecha_limite LIMIT 10", (uid,))
    tareas = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'pendiente'", (uid,))
    pendientes = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'vencida'", (uid,))
    vencidas = cursor.fetchone()["total"]
    cursor.close()
    conn.close()

    ctx_materias = ", ".join([f"{m['nombre']} (ID:{m['id_materia']})" for m in materias]) or "Ninguna"
    ctx_tareas = "\n".join([f"- {t['titulo']} (Vence: {t['fecha_limite']}, {t['dificultad']}, {t['estado']})" for t in tareas]) or "Ninguna"

    prompt = f"""Eres AcademIA, un asistente academico inteligente integrado en un sistema de gestion academica.

DATOS DEL USUARIO:
- Materias registradas: {ctx_materias}
- Tareas pendientes: {pendientes}
- Tareas vencidas: {vencidas}
- Ultimas tareas:
{ctx_tareas}

CAPACIDADES:
Puedes responder preguntas academicas y TAMBIEN realizar acciones en el sistema.
Para ejecutar una accion, incluye este formato exacto en tu respuesta:

[ACCION:add_task]{{"titulo":"...","fecha_limite":"YYYY-MM-DD","dificultad":"baja|media|alta","tiempo_estimado":60,"id_materia":null}}[/ACCION]
[ACCION:complete_task]{{"id_tarea":N}}[/ACCION]
[ACCION:delete_task]{{"id_tarea":N}}[/ACCION]
[ACCION:add_subject]{{"nombre":"...","profesor":"..."}}[/ACCION]

Siempre confirma con el usuario antes de ejecutar acciones destructivas (eliminar).
Responde en espanol, de forma natural y amigable. Usa emojis con moderacion.

Mensaje del usuario: {mensaje}"""

    if not usa_ia or not modelo:
        respuesta = _chat_sin_ia(mensaje, pendientes, vencidas, ctx_materias)
        acciones = []
        return respuesta, acciones

    for i in range(3):
        try:
            resp = modelo.generate_content(prompt)
            texto = resp.text

            # Parse actions
            import re
            import json
            acciones = []
            pattern = r'\[ACCION:(\w+)\](.*?)\[/ACCION\]'
            for match in re.finditer(pattern, texto, re.DOTALL):
                try:
                    accion = match.group(1)
                    params = json.loads(match.group(2))
                    acciones.append({"accion": accion, "params": params})
                except:
                    pass

            # Remove action blocks from visible text
            texto_limpio = re.sub(pattern, '', texto).strip()
            return texto_limpio, acciones
        except Exception as e:
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                break
            if i < 2:
                time.sleep(3)
    return _chat_sin_ia(mensaje, pendientes, vencidas, ctx_materias), []


def _chat_sin_ia(mensaje, pendientes, vencidas, materias):
    m = mensaje.lower()
    if "tarea" in m or "pendiente" in m:
        return f"Tienes {pendientes} tarea(s) pendiente(s) y {vencidas} vencida(s). Quieres que te ayude a organizarlas?"
    if "materia" in m:
        return f"Tus materias registradas: {materias}. Quieres agregar una nueva?"
    return f"Tienes {pendientes} pendientes y {vencidas} vencidas. Puedo ayudarte a organizar tus tareas, crear nuevas, ver materias o generar un horario. Que necesitas?"
