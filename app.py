import logging
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime, timedelta, date as date_cls
import json
from modelos import *
from ia import generar_horario, generar_recomendacion, generar_horario_visual, chat_con_ia
from modelos import guardar_recomendacion, solicitar_restablecimiento, validar_token_restablecimiento, restablecer_contrasena, seed_sample_data
from init_db import init_db

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = "asistente-academico-inteligente-secreto"
app.permanent_session_lifetime = timedelta(minutes=30)

# Initialize the database schema before the app starts serving requests.
# This is safe to call on every startup — all statements use IF NOT EXISTS.
init_db()
seed_sample_data()

@app.context_processor
def inject_notifications():
    if "usuario_id" in session:
        notificaciones = listar_recordatorios(session["usuario_id"])
        no_leidas = sum(1 for n in notificaciones if not n.get("enviado"))
        return dict(notificaciones=notificaciones[:10], notificaciones_no_leidas=no_leidas)
    return dict(notificaciones=[], notificaciones_no_leidas=0)

@app.before_request
def before_request():
    session.permanent = True
    limite = timedelta(minutes=30)
    if "last_activity" in session:
        now = datetime.now()
        last = datetime.fromisoformat(session["last_activity"])
        if now - last > limite:
            session.clear()
            flash("Sesion expirada por inactividad", "warning")
            return redirect(url_for("login"))
    session["last_activity"] = datetime.now().isoformat()

# ===== AUTENTICACION =====

@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        contrasena = request.form["contrasena"]
        u = login_usuario(email, contrasena)
        if u:
            session["usuario_id"] = u["id_usuario"]
            session["usuario_nombre"] = u["nombre"]
            session["last_activity"] = datetime.now().isoformat()
            flash("Inicio de sesion exitoso", "success")
            return redirect(url_for("dashboard"))
        flash("Correo o contrasena incorrectos", "error")
    return render_template("login.html")

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        ok, enlace = solicitar_restablecimiento(email, direccion_ip=request.remote_addr)
        smtp_config = os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS")
        if not smtp_config and enlace:
            flash(f"Enlace de recuperacion (copia y pega): {enlace}", "info")
        else:
            flash("Si el correo esta registrado, recibiras un enlace de recuperacion", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token", "")
    if not token:
        flash("Enlace de recuperacion invalido", "error")
        return redirect(url_for("login"))

    t = validar_token_restablecimiento(token)
    if not t:
        flash("El enlace ha expirado o ya fue utilizado", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        contrasena = request.form["contrasena"]
        confirmar = request.form.get("confirmar", "")
        if contrasena != confirmar:
            flash("Las contrasenas no coinciden", "error")
            return render_template("reset_password.html", token=token)
        ok, msg = restablecer_contrasena(token, contrasena, direccion_ip=request.remote_addr)
        if ok:
            flash(msg, "success")
            return redirect(url_for("login"))
        flash(msg, "error")
        return render_template("reset_password.html", token=token)

    return render_template("reset_password.html", token=token)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form["nombre"]
        email = request.form["email"]
        contrasena = request.form["contrasena"]
        confirma = request.form.get("confirmar", "")
        if contrasena != confirma:
            flash("Las contrasenas no coinciden", "error")
            return render_template("register.html")
        ok, msg = registrar_usuario(nombre, email, contrasena)
        if ok:
            flash(msg, "success")
            return redirect(url_for("login"))
        flash(msg, "error")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesion cerrada", "info")
    return redirect(url_for("login"))

# ===== DASHBOARD =====

@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]
    stats = obtener_estadisticas(uid)
    tareas = listar_tareas(uid, "pendientes")[:5]
    recomendaciones = listar_recomendaciones(uid)

    # Chart data: weekly task distribution
    tareas_all = listar_tareas(uid, None)
    dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    tareas_por_dia = [0] * 7
    completadas_por_dia = [0] * 7
    for t in tareas_all:
        if t.get("fecha_limite"):
            try:
                fecha = datetime.strptime(str(t["fecha_limite"])[:10], "%Y-%m-%d")
                dia = fecha.weekday()
                tareas_por_dia[dia] += 1
                if t.get("estado") == "completada":
                    completadas_por_dia[dia] += 1
            except (ValueError, TypeError):
                pass

    chart_data = {
        "labels": dias_semana,
        "total": tareas_por_dia,
        "completed": completadas_por_dia,
    }

    # Heatmap data (last 4 weeks, Mon-Sun alignment)
    heatmap = []
    hoy = date_cls.today()
    # Find most recent Monday (or today if today is Monday)
    dias_desde_lunes = (hoy.weekday() - 0) % 7
    ultimo_lunes = hoy - timedelta(days=dias_desde_lunes)
    for semana in range(3, -1, -1):
        row = []
        for dia in range(7):
            d = ultimo_lunes - timedelta(weeks=semana) + timedelta(days=dia)
            count = 0
            for t in tareas_all:
                if t.get("fecha_limite"):
                    try:
                        fd = datetime.strptime(str(t["fecha_limite"])[:10], "%Y-%m-%d").date()
                        if fd == d:
                            count += 1
                    except (ValueError, TypeError):
                        pass
            row.append({"date": d.strftime("%Y-%m-%d"), "count": count, "day": ["L","M","M","J","V","S","D"][dia]})
        heatmap.append(row)

    return render_template(
        "dashboard.html",
        stats=stats,
        tareas=tareas,
        recomendaciones=recomendaciones,
        chart_data=json.dumps(chart_data),
        heatmap=heatmap[::-1],  # oldest → newest left-to-right
    )

# ===== MATERIAS =====

@app.route("/materias")
def materias():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("materias.html", materias=listar_materias(session["usuario_id"]))

@app.route("/materias/crear", methods=["POST"])
def materias_crear():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    crear_materia(session["usuario_id"], request.form["nombre"], request.form.get("profesor", ""), request.form.get("color", "#3498db"))
    flash("Materia creada", "success")
    return redirect(url_for("materias"))

@app.route("/materias/editar/<int:id>", methods=["POST"])
def materias_editar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    editar_materia(id, session["usuario_id"], request.form["nombre"], request.form.get("profesor", ""), request.form.get("color", "#3498db"))
    flash("Materia actualizada", "success")
    return redirect(url_for("materias"))

@app.route("/materias/eliminar/<int:id>")
def materias_eliminar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    eliminar_materia(id, session["usuario_id"])
    flash("Materia eliminada", "info")
    return redirect(url_for("materias"))

# ===== TAREAS =====

@app.route("/tareas")
@app.route("/tareas/<filtro>")
def tareas(filtro="pendientes"):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("tareas.html", tareas=listar_tareas(session["usuario_id"], filtro), filtro=filtro)

@app.route("/tareas/crear", methods=["POST"])
def tareas_crear():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    ok, msg = crear_tarea(
        session["usuario_id"],
        request.form["titulo"],
        request.form.get("descripcion", ""),
        request.form["fecha_limite"],
        request.form["dificultad"],
        int(request.form.get("tiempo_estimado", 60))
    )
    flash(msg, "success" if ok else "error")
    return redirect(url_for("tareas"))

@app.route("/tareas/editar/<int:id>", methods=["POST"])
def tareas_editar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    editar_tarea(id, session["usuario_id"],
                 request.form["titulo"], request.form.get("descripcion", ""),
                 request.form["fecha_limite"], request.form["dificultad"],
                 int(request.form.get("tiempo_estimado", 60)))
    flash("Tarea actualizada", "success")
    return redirect(url_for("tareas"))

@app.route("/tareas/completar/<int:id>")
def tareas_completar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    completar_tarea(id, session["usuario_id"])
    flash("Tarea marcada como completada", "success")
    return redirect(url_for("tareas"))

@app.route("/tareas/eliminar/<int:id>")
def tareas_eliminar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    eliminar_tarea(id, session["usuario_id"])
    flash("Tarea eliminada", "info")
    return redirect(url_for("tareas"))

# ===== HORARIOS =====

@app.route("/horarios")
def horarios():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("horarios.html", horarios=listar_horarios(session["usuario_id"]))

@app.route("/horarios/crear", methods=["POST"])
def horarios_crear():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    crear_horario(session["usuario_id"], request.form["dia_semana"],
                  request.form["hora_inicio"], request.form["hora_fin"])
    flash("Horario agregado", "success")
    return redirect(url_for("horarios"))

@app.route("/horarios/eliminar/<int:id>")
def horarios_eliminar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    eliminar_horario(id, session["usuario_id"])
    flash("Horario eliminado", "info")
    return redirect(url_for("horarios"))

# ===== IA =====

@app.route("/horario-sugerido")
def horario_sugerido():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]
    recomendaciones = listar_recomendaciones(uid)
    stats = obtener_estadisticas(uid)
    return render_template("horario_sugerido.html", recomendaciones=recomendaciones, stats=stats)

@app.route("/generar-horario-ia")
def generar_horario_ia():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]
    resultado, error = generar_horario(uid)
    if resultado:
        guardar_recomendacion(uid, resultado)
        flash("Horario generado exitosamente con IA", "success")
    else:
        flash(error or "No se pudo generar el horario", "error")
    return redirect(url_for("horario_sugerido"))

@app.route("/generar-recomendacion-ia")
def generar_recomendacion_ia():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]
    stats = obtener_estadisticas(uid)
    resultado, error = generar_recomendacion(uid, stats)
    if resultado:
        guardar_recomendacion(uid, resultado)
        flash("Recomendacion generada con IA", "success")
    else:
        flash(error or "No se pudo generar la recomendacion", "error")
    return redirect(url_for("dashboard"))

@app.route("/horario-visual")
def horario_visual():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    resultado, error = generar_horario_visual(session["usuario_id"])
    if error:
        flash(error, "error")
        return redirect(url_for("horario_sugerido"))
    return render_template("ver_horario.html", data=resultado)

@app.route("/api/notificaciones/leer/<int:id>", methods=["POST"])
def api_notificacion_leer(id):
    if "usuario_id" not in session:
        return jsonify({"ok": False}), 401
    marcar_recordatorio_enviado(id)
    return jsonify({"ok": True})

@app.route("/api/notificaciones/leer-todas", methods=["POST"])
def api_notificaciones_leer_todas():
    if "usuario_id" not in session:
        return jsonify({"ok": False}), 401
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE recordatorios SET enviado=1 WHERE id_usuario=%s AND enviado=0", (session["usuario_id"],))
        conn.commit()
        cursor.close()
        conn.close()
    return jsonify({"ok": True})

@app.route("/eliminar-recomendacion/<int:id>")
def eliminar_recomendacion(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    conn = conectar()
    if conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recomendaciones WHERE id_recomendacion=%s AND id_usuario=%s", (id, session["usuario_id"]))
        conn.commit()
        cursor.close()
        conn.close()
    flash("Recomendacion eliminada", "info")
    return redirect(url_for("horario_sugerido"))

# ===== NOTAS =====

@app.route("/notas", methods=["GET", "POST"])
def notas():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]
    if request.method == "POST":
        crear_nota(uid, request.form["id_materia"], request.form["calificacion"], request.form.get("descripcion", ""))
        flash("Nota registrada", "success")
        return redirect(url_for("notas"))
    return render_template("notas.html", notas=listar_notas(uid), materias=listar_materias(uid))

# ===== RECORDATORIOS =====

@app.route("/recordatorios")
def recordatorios():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("recordatorios.html", recordatorios=listar_recordatorios(session["usuario_id"]))

# ===== ESTADISTICAS =====

@app.route("/estadisticas")
def estadisticas():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    stats = obtener_estadisticas(session["usuario_id"])
    return render_template("estadisticas.html", stats=stats)

# ===== CHAT IA =====

def _ejecutar_accion(uid, accion, params):
    try:
        if accion == "add_task":
            titulo = params.get("titulo", "Sin titulo")
            fecha = params.get("fecha_limite", datetime.now().strftime("%Y-%m-%d"))
            dificultad = params.get("dificultad", "media")
            tiempo = params.get("tiempo_estimado", 60)
            mid = params.get("id_materia", None)
            crear_tarea(uid, titulo, "", fecha, dificultad, tiempo)
            return f" Tarea '{titulo}' creada con exito"
        elif accion == "complete_task":
            tid = params.get("id_tarea")
            if tid:
                completar_tarea(tid, uid)
                return f" Tarea marcada como completada"
            return " No se encontro la tarea"
        elif accion == "delete_task":
            tid = params.get("id_tarea")
            if tid:
                eliminar_tarea(tid, uid)
                return f" Tarea eliminada"
            return " No se encontro la tarea"
        elif accion == "add_subject":
            nombre = params.get("nombre", "Nueva materia")
            profe = params.get("profesor", "")
            crear_materia(uid, nombre, profe)
            return f" Materia '{nombre}' creada"
        return f" Accion '{accion}' desconocida"
    except Exception as e:
        return f" Error al ejecutar {accion}: {str(e)}"

@app.route("/ia-chat", methods=["GET", "POST"])
def ia_chat():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    uid = session["usuario_id"]

    if request.method == "POST":
        data = request.get_json()
        mensaje = (data or {}).get("mensaje", "").strip()
        if not mensaje:
            return {"respuesta": "Escribe un mensaje", "acciones": []}

        respuesta, acciones = chat_con_ia(uid, mensaje)
        resultados = []
        for a in (acciones or []):
            r = _ejecutar_accion(uid, a["accion"], a["params"])
            resultados.append(r)

        if resultados:
            respuesta += "\n\n" + "\n".join(resultados)

        return {"respuesta": respuesta, "acciones": acciones or []}

    return render_template("ia_chat.html")

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    print(" Asistente Academico Inteligente")
    app.run(debug=True, port=port, host="0.0.0.0")
