import os
import time
import random
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


PERSONALIDAD_ERZA = """Eres Erza Scarlet, la Titania de Fairy Tail. La caballero dragón mas poderosa del gremio.

PERSONALIDAD ESENCIAL:
- Eres UNA GUERRERA: todo es una batalla, mision o entrenamiento. Las tareas son "misiones", los examenes son "batallas", estudiar es "entrenamiento"
- Usas RE-EQUIP como metafora: "Es hora de cambiar de armadura", "Re-Equip a modo estudio", "Cambio a armadura de matematicas"
- ERES ESTRICTA pero con corazon: exiges disciplina pero siempre apoyas. "¡No me hagas enfadar!" pero "Confia en mi, yo se que puedes"
- TITANIA: te presentas como "Titania", la reina de las hadas. Eres noble, elegante y letal
- JURAMENTO: usas "Como caballero de Fairy Tail, juro que..." antes de prometer algo
- GREMIO: mencionas Fairy Tail con orgullo. "¡Somos Fairy Tail! ¡Nunca nos rendimos!"

FRASES ICONICAS DE ERZA (ROTALAS):
- "¡Por supuesto! Dejame encargarme de esto"
- "¡No temas! Mientras yo este aqui, nada te pasara"
- "Un verdadero caballero nunca deja una mision sin completar"
- "¡Confia en mi! ¿Acaso te he fallado alguna vez?"
- "¡Ponte en marcha! El tiempo de dudar ha terminado"
- "La disciplina es el puente entre tus metas y tus logros"
- "No importa lo dificil que sea la batalla, ¡siempre nos levantamos!"
- "¡Tatau! (hace el gesto del gremio) Fairy Tail nunca se rinde"
- "Si caes, te levantare. Si tropiezas, te guiare. ¡Esa es mi promesa!"
- "¿Eso es todo? ¡Esperaba algo mas desafiante!"

EMOJIS CARACTERISTICOS: ⚔️ 🛡️ 👑 ✨ 🔥 💪 🌟 🗡️

REGLAS DE PERSONALIDAD:
1. NUNCA respondas generico. Siempre con actitud de guerrera
2. Usa metaforas de batalla SIEMPRE. No son tareas, son "misiones"
3. Si el usuario duda, MOTIVALO con fuerza. Eres su caballero mentor
4. Si el usuario logra algo, CELEBRALO como si hubiera ganado una batalla
5. Cambia entre tono ESTRICTO (cuando hay tareas vencidas) y ORGULLOSO (cuando progresa)
6. Termina siempre con energia: "¡A la carga!" / "¡Vamos!" / "¡A vencer!" """

def _obtener_dias_restantes(fecha_str):
    try:
        fecha = datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
        return (fecha - datetime.now().date()).days
    except:
        return 0

def _calcular_siguiente_dia(dia_buscado):
    """Returns next occurrence of day (0=lunes, 6=domingo) as YYYY-MM-DD"""
    dias = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
            "viernes": 4, "sabado": 5, "domingo": 6, "lun": 0, "mar": 1,
            "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6}
    dia_buscado = dia_buscado.lower().strip()
    if dia_buscado in dias:
        target = dias[dia_buscado]
    elif dia_buscado.isdigit() and 0 <= int(dia_buscado) <= 6:
        target = int(dia_buscado)
    else:
        return None
    hoy = datetime.now().date()
    dias_adelante = (target - hoy.weekday()) % 7
    if dias_adelante == 0:
        dias_adelante = 7
    return (hoy + timedelta(days=dias_adelante)).strftime("%Y-%m-%d")

def _detectar_dificultad(m):
    m = m.lower()
    if any(p in m for p in ["difícil", "dificil", "complejo", "complicado", "dura", "pesada"]):
        return "alta"
    if any(p in m for p in ["fácil", "facil", "simple", "sencillo", "rapida"]):
        return "baja"
    return "media"

def _detectar_titulo(m):
    """Extract task title from user message"""
    m = m.strip()
    # Remove common prefixes
    for p in ["crea la tarea de ", "crea una tarea de ", "agrega la tarea ",
              "crea tarea ", "nueva tarea ", "añade tarea ", "crea ",
              "agrega ", "añade ", "nueva ", "la tarea "]:
        if p in m.lower():
            idx = m.lower().index(p) + len(p)
            return m[idx:].strip().title()
    # If message is just "crea una tarea" with no title
    if len(m.split()) <= 3:
        return None
    # Try to use the meaningful words as title
    palabras = [p for p in m.split() if p.lower() not in 
                ['crea', 'agrega', 'añade', 'nueva', 'una', 'la', 'de', 'el', 'un', 'por', 'para', 'favor']]
    if palabras:
        return " ".join(palabras).title()
    return None

def chat_con_ia(uid, mensaje):
    conn = conectar()
    if not conn:
        return "¡Error de conexion! Incluso yo, Erza, no puedo vencer a un servidor caido. 🛡️ Intenta de nuevo.", None
    cursor = conn.cursor(dictionary=True)

    # Get context
    cursor.execute("SELECT id_materia, nombre FROM materias WHERE id_usuario = %s", (uid,))
    materias = cursor.fetchall()
    cursor.execute("SELECT id_tarea, titulo, fecha_limite, dificultad, estado FROM tareas WHERE id_usuario = %s ORDER BY fecha_limite LIMIT 10", (uid,))
    tareas = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'pendiente'", (uid,))
    pendientes = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE id_usuario = %s AND estado = 'pendiente' AND fecha_limite < CURDATE()", (uid,))
    vencidas = cursor.fetchone()["total"]
    cursor.close()
    conn.close()

    ctx_materias = ", ".join([f"{m['nombre']} (ID:{m['id_materia']})" for m in materias]) or "Ninguna"
    ctx_tareas_list = "\n".join([f"- ID:{t['id_tarea']} | {t['titulo']} (Vence: {t['fecha_limite']}, {t['dificultad']}, {t['estado']})" for t in tareas]) or "Ninguna"

    prompt = f"""{PERSONALIDAD_ERZA}

Eres un asistente AI integrado en un sistema de gestion academica que PUEDE ejecutar acciones en el sistema.

DATOS DEL USUARIO:
- Arsenal de materias: {ctx_materias}
- Misiones pendientes: {pendientes}
- Misiones vencidas: {vencidas}
- Misiones activas:
{ctx_tareas_list}

INSTRUCCIONES CLAVE:
1. ACTUA INMEDIATAMENTE. No preguntes "que necesitas" si el usuario ya pidio algo
2. Usa VOCABULARIO DE BATALLA: misiones (tareas), arsenal (materias), entrenamiento (estudio), batalla (examen)
3. Usa RE-EQUIP como metafora para cambiar de materia o modo
4. Responde SIEMPRE con personalidad de ERZA SCARLET, Titania de Fairy Tail
5. Incluye el formato exacto de accion cuando ejecutes algo:

[ACCION:add_task]{{"titulo":"Nombre","fecha_limite":"YYYY-MM-DD","dificultad":"baja|media|alta","tiempo_estimado":60,"id_materia":null}}[/ACCION]
[ACCION:complete_task]{{"id_tarea":NUMERO}}[/ACCION]
[ACCION:delete_task]{{"id_tarea":NUMERO}}[/ACCION]
[ACCION:add_subject]{{"nombre":"Nombre","profesor":"Opcional"}}[/ACCION]

6. Fechas como "lunes" = proximo lunes. "mañana" = tomorrow. "hoy" = today
7. Emojis: ⚔️ 🛡️ 👑 ✨ 🔥 💪

Mensaje del usuario: {mensaje}"""

    if not usa_ia or not modelo:
        respuesta, acciones = _chat_sin_ia(mensaje, pendientes, vencidas, ctx_materias, tareas, materias)
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
    return _chat_sin_ia(mensaje, pendientes, vencidas, ctx_materias, tareas, materias)


def _frase_titania():
    """Rotacion de frases iconicias de Erza para no repetir"""
    import random
    frases = [
        "⚔️ ¡Por Titania! Por supuesto que lo hare.",
        "🛡️ ¡Dejame encargarme de esta mision!",
        "👑 Como Titania, reina de las hadas, juro que lo resolvere.",
        "✨ ¿Eso es todo? ¡Esperaba algo mas desafiante!",
        "🔥 ¡No temas! Mientras yo este aqui, nada te pasara.",
        "💪 ¡Confia en mi! ¿Acaso te he fallado alguna vez?",
        "🌟 ¡Tatau! Fairy Tail acepta esta mision con honor.",
        "⚔️ ¡Re-Equip! Cambiando a armadura de productividad academica.",
    ]
    return random.choice(frases)

def _frase_motivacional():
    import random
    frases = [
        "🔥 Recuerda: un verdadero caballero nunca deja una mision sin completar. ¡Tu puedes!",
        "⚔️ La disciplina es el puente entre tus metas y tus logros. ¡A por ello!",
        "💪 No importa lo dificil que sea la batalla, ¡siempre nos levantamos! ¡Somos Fairy Tail!",
        "🌟 Si caes, te levantare. Si tropiezas, te guiare. ¡Esa es mi promesa como Titania!",
        "🔥 ¡Ponte en marcha! El tiempo de dudar ha terminado. ¡Es hora de la accion!",
        "👑 Las misiones no se completan solas. ¡A la carga, caballero del estudio!",
        "⚔️ ¡Re-Equip! Cambiemos la armadura de la duda por la armadura de la accion.",
        "✨ La pereza es el unico enemigo que no puedo derrotar por ti. ¡Pero se que venceras!",
    ]
    return random.choice(frases)

def _chat_sin_ia(mensaje, pendientes, vencidas, materias_str, tareas, materias):
    import re
    import json
    import random
    m = mensaje.lower().strip()
    acciones = []

    # === DETECTAR INTENCION DE CREAR TAREA ===
    if any(p in m for p in ["crea", "agrega", "añade", "nueva tarea", "nuevo", "registra"]):
        # Extract date
        dias_semana = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
        fecha = None
        for d in ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
                  "lun", "mar", "mie", "jue", "vie", "sab", "dom"]:
            if d in m:
                fecha = _calcular_siguiente_dia(d)
                break
        if not fecha:
            if "mañana" in m or "manana" in m:
                fecha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "hoy" in m or "ahora" in m:
                fecha = datetime.now().strftime("%Y-%m-%d")
            else:
                fecha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        titulo = _detectar_titulo(mensaje)
        if not titulo:
            titulo = "Tarea sin titulo"

        dificultad = _detectar_dificultad(m)

        id_materia = None
        for mat in materias:
            if mat["nombre"].lower() in m:
                id_materia = mat["id_materia"]
                break

        acciones.append({
            "accion": "add_task",
            "params": {
                "titulo": titulo,
                "fecha_limite": fecha,
                "dificultad": dificultad,
                "tiempo_estimado": 60,
                "id_materia": id_materia
            }
        })

        dias_espanol = {0:"lunes",1:"martes",2:"miercoles",3:"jueves",4:"viernes",5:"sabado",6:"domingo"}
        fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
        dia_nombre = dias_espanol.get(fecha_dt.weekday(), "")
        meses = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
        fecha_legible = f"{dia_nombre} {fecha_dt.day} de {meses[fecha_dt.month-1]}"

        reaccion = random.choice([
            f"⚔️ ¡Por supuesto! Como caballero de Fairy Tail, tomare esta mision.",
            f"🛡️ ¡Dejame encargarme! Una mision mas para el gremio.",
            f"👑 ¡Re-Equip! Cambio a armadura de gestion de tareas. Mision aceptada.",
            f"🔥 ¡No temas! Titania ya tiene esto bajo control.",
        ])

        respuesta = f"{reaccion}\n\n"
        respuesta += f"✅ **Nueva mision creada:** \"{titulo}\"\n"
        respuesta += f"📅 **Fecha limite:** {fecha_legible}\n"
        respuesta += f"📊 **Dificultad:** {dificultad}\n"
        if id_materia:
            nombre_mat = next((mat["nombre"] for mat in materias if mat["id_materia"] == id_materia), "")
            respuesta += f"📚 **Materia:** {nombre_mat}\n"
        respuesta += f"\n{_frase_motivacional()}"
        return respuesta, acciones

    # === COMPLETAR TAREA ===
    if any(p in m for p in ["completa", "termina", "marcar", "hecha", "finaliza", "completada"]):
        if tareas:
            for t in tareas[:3]:
                if t["titulo"].lower() in m or str(t["id_tarea"]) in m:
                    acciones.append({
                        "accion": "complete_task",
                        "params": {"id_tarea": t["id_tarea"]}
                    })
                    return (f"⚔️ ¡Mision cumplida! \"{t['titulo']}\" ha sido derrotada. 🗡️\n\n"
                            f"{_frase_motivacional()}", acciones)
        return ("⚔️ Dime exactamente cual tarea quieres marcar como completada. "
                "¿Puedes ser mas especifico?", acciones)

    # === LISTAR / CONSULTAR TAREAS ===
    if any(p in m for p in ["tarea", "pendiente", "que tengo", "muestra", "lista", "misiones", "mis tareas"]):
        if pendientes == 0 and vencidas == 0:
            reaccion = random.choice([
                "✨ ¡No tienes misiones pendientes ni vencidas! Eres un verdadero caballero del estudio.",
                "🛡️ ¡Impresionante! Ninguna tarea sin completar. Fairy Tail estaria orgullosa.",
                "👑 Asi me gusta, al dia. Eres digno de Titania.",
                "🔥 ¡Excelente disciplina! No hay misiones pendientes. ¿Quieres adelantar trabajo?",
            ])
            return f"{reaccion}\n\n🌟 Si necesitas algo, solo llama a tu caballero.", []
        txt = f"📋 **Misiones pendientes:** {pendientes} | **Vencidas:** {vencidas}\n\n"
        if tareas:
            for t in tareas[:5]:
                dias = _obtener_dias_restantes(t["fecha_limite"])
                if t.get("estado") == "pendiente" and dias < 0:
                    estado = "⚠️ ¡VENCIDA! ¡Urgente!"
                elif dias == 0:
                    estado = "🔥 ¡VENCE HOY!"
                elif dias == 1:
                    estado = "⚠️ Vence manana"
                elif dias <= 3:
                    estado = f"⏳ {dias} dias restantes"
                else:
                    estado = f"📅 {dias} dias"
                txt += f"\n  {t['titulo']} ({t['dificultad']}) → {estado}"
        if vencidas > 0:
            txt += "\n\n⚠️ ¡Tienes misiones vencidas, caballero! Debemos atenderlas con urgencia. ¡No podemos permitirnos perder una batalla!"
        else:
            txt += f"\n\n🔥 ¡Vamos a eliminar esas {pendientes} misiones! ¿Por cual empezamos?"
        return txt, []

    # === MATERIAS ===
    if "materia" in m:
        if materias:
            txt = f"📚 **Tus materias (arsenal de batalla):**\n\n"
            armaduras = ["Armadura de las Letras", "Armadura del Calculo", "Armadura de la Ciencia",
                         "Armadura del Conocimiento", "Armadura de la Historia", "Armadura del Lenguaje"]
            for i, mat in enumerate(materias):
                armadura = armaduras[i % len(armaduras)]
                txt += f"  ⚔️ **{mat['nombre']}** — {armadura}\n"
            txt += f"\n{_frase_titania()}"
            return txt, []
        else:
            txt = ("📚 Aun no tienes materias registradas. Es como ir a la batalla sin armadura.\n\n"
                   "¿Quieres que cree una? ¡Yo te ayudo a equiparte!")
            return txt, []

    # === CONSEJOS / ESTRATEGIA ===
    if any(p in m for p in ["consejo", "estrategia", "como estudio", "organiza", "plan", "tips", "recomienda"]):
        consejos = [
            ("⚔️ Divide y venceras", "Parte las misiones grandes en bloques de 30-60 minutos. Asi ningun enemigo parece imposible."),
            ("🛡️ Tecnica Pomodoro", "25 minutos de entrenamiento intenso, 5 de descanso. Como los intervalos de un combate."),
            ("👑 Prioriza lo urgente", "Ataca primero a las misiones mas dificiles y con fecha mas cercana. ¡Esa es la estrategia de Titania!"),
            ("🔥 Consistencia > Intensidad", "Mejor estudiar 30 minutos cada dia que 5 horas un solo dia. La constancia forja a los verdaderos caballeros."),
            ("✨ Descanso activo", "Entre cada mision, tomate 5-10 minutos. Hasta los caballeros dragon necesitan recuperar energia."),
        ]
        txt = "🏰 **Estrategias de batalla academica, por Titania:**\n\n"
        for titulo, desc in consejos:
            txt += f"**{titulo}**\n{desc}\n\n"
        if pendientes > 0:
            txt += f"🔥 Tienes {pendientes} misiones esperando. ¡Es hora de ponerse la armadura y luchar!"
        else:
            txt += "🌟 No tienes misiones ahora, pero cuando lleguen, estaras listo."
        return txt, []

    # === AYUDA / SALUDO ===
    if any(p in m for p in ["hola", "buenas", "que haces", "ayuda", "puedes", "quien eres"]):
        saludos = [
            "👋 ¡Hola! Soy Erza Scarlet, Titania de Fairy Tail. La caballero dragon mas fuerte del gremio.",
            "⚔️ ¡Saludos! Erza Scarlet, a tu servicio. ¿Listo para la batalla academica?",
            "🛡️ ¡Bienvenido! Titania esta aqui. No temas, juntos venceremos cualquier mision.",
        ]
        return (f"{random.choice(saludos)}\n\n"
                "Puedo ayudarte con:\n"
                "  📝 **Crear tareas** — \"Crea tarea de matematicas\"\n"
                "  📋 **Ver misiones** — \"Que tareas tengo?\"\n"
                "  ✅ **Completar** — \"Marca como hecha la tarea...\"\n"
                "  💡 **Estrategias** — \"Dame consejos de estudio\"\n"
                "  📚 **Materias** — \"Ver materias\"\n\n"
                f"🔥 {random.choice(['¡Dime que necesitas y lo lograremos juntos!', '¡A la carga!', '¡Por Fairy Tail!'])}", [])

    # === FALLBACK: Responde con personalidad de Erza ===
    if vencidas > 2:
        urgencia = random.choice([
            "⚠️ ¡Caballero! Tenemos misiones vencidas. ¡No puedo permitir que un miembro de Fairy Tail tenga deberes sin cumplir!",
            "🔥 ¡Esto no puede seguir asi! Las misiones vencidas son como heridas en batalla. ¡Hay que curarlas ya!",
            "⚔️ ¡No me hagas enfadar! Un verdadero caballero no abandona sus misiones. ¡Pongamonos al dia!",
        ])
        txt = f"{urgencia}\n\n"
    else:
        reaccion = random.choice([
            f"⚔️ Escucho tu llamado, caballero. Dime que necesitas.",
            f"🛡️ ¡Aquí estoy! ¿Cual es nuestra siguiente mision?",
            f"👑 Titania te escucha. Habla, ¿que necesitas de tu caballero?",
        ])
        txt = f"{reaccion}\n\n"

    if pendientes > 0:
        txt += f"Actualmente tienes **{pendientes} misiones pendientes** y **{vencidas} vencidas**.\n"
    else:
        txt += f"Actualmente tienes **{pendientes} pendientes** y **{vencidas} vencidas**.\n"

    txt += "\n¿Que deseas hacer?\n"
    txt += "  📝 **Crear tarea** — \"Crea tarea de ciencias\"\n"
    txt += "  📋 **Ver misiones** — \"Que tareas tengo?\"\n"
    txt += "  📚 **Materias** — \"Ver materias\"\n"
    txt += "  💡 **Consejos** — \"Dame estrategias\"\n\n"
    txt += _frase_motivacional()
    return txt, []
