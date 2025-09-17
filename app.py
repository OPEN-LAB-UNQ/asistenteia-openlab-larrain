import os
from flask import Flask

# === Importación de Blueprints necesarios ===
from foro import foro_bp
from curso import curso_bp

# === Inicialización ===
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = "unaClaveMuySegura123"

# === Registro de Blueprints activos ===
app.register_blueprint(foro_bp, url_prefix='/foro')
app.register_blueprint(curso_bp, url_prefix='/curso')

# === Export para Gunicorn ===
application = app

# === Modo local (debug) ===
if __name__ == "__main__":
    app.run(debug=True)
