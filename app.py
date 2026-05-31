from flask import Flask, render_template, request
import os

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analizar", methods=["POST"])
def analizar():
    cargo = request.form["cargo"]
    requisitos = request.form["requisitos"]
    archivos = request.files.getlist("cvs")

    resultados = []

    for archivo in archivos:
        ruta = os.path.join(app.config["UPLOAD_FOLDER"], archivo.filename)
        archivo.save(ruta)

        resultados.append({
            "nombre": archivo.filename,
            "compatibilidad": 80,
            "estado": "Preseleccionado"
        })

    return render_template("resultados.html", resultados=resultados, cargo=cargo)

@app.route("/candidato")
def candidato():
    return render_template("candidato.html")

@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        total_candidatos=len(candidatos),
        total_vacantes=len(vacantes)
    )

candidatos = []

@app.route("/registrar_candidato", methods=["POST"])
def registrar_candidato():
    nombre = request.form["nombre"]
    correo = request.form["correo"]
    telefono = request.form["telefono"]
    cv = request.files["cv"]

    ruta = os.path.join(app.config["UPLOAD_FOLDER"], cv.filename)
    cv.save(ruta)

    candidatos.append({
        "nombre": nombre,
        "correo": correo,
        "telefono": telefono,
        "cv": cv.filename
    })

    return render_template("confirmacion.html", nombre=nombre)


@app.route("/candidatos")
def ver_candidatos():
    return render_template("candidatos.html", candidatos=candidatos)

vacantes = []
@app.route("/vacante")
def vacante():
    return render_template("vacante.html")


@app.route("/guardar_vacante", methods=["POST"])
def guardar_vacante():

    cargo = request.form["cargo"]
    empresa = request.form["empresa"]
    requisitos = request.form["requisitos"]
    experiencia = request.form["experiencia"]

    vacantes.append({
        "cargo": cargo,
        "empresa": empresa,
        "requisitos": requisitos,
        "experiencia": experiencia
    })

    return "Vacante registrada correctamente"

@app.route("/vacantes")
def ver_vacantes():
    return render_template(
        "vacantes.html",
        vacantes=vacantes
    )

@app.route("/analisis")
def analisis():
    return render_template("analisis.html")


@app.route("/ranking")
def ranking():
    return render_template("ranking.html")


@app.route("/acerca")
def acerca():
    return render_template("acerca.html")

if __name__ == "__main__":
    app.run(debug=True)

