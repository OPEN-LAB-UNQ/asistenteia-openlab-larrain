from flask import Blueprint, jsonify
import mysql.connector
from mysql.connector import pooling
import os
import time
from dotenv import load_dotenv
import traceback

# Forzar carga del .env desde su ruta absoluta
load_dotenv(dotenv_path="/home/asistenteia/.env")

curso_bp = Blueprint("curso", __name__)

DB_PREFIX = os.getenv("DB_PREFIX")
if not DB_PREFIX:
    raise ValueError("⚠️ Debes definir DB_PREFIX en el archivo .env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT", 3306)),
}

POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

# Log para depuración
print("=== Configuración de curso.py ===")
for k, v in DB_CONFIG.items():
    if k != "password":
        print(f"{k}: {v}")
print(f"DB_PREFIX: {DB_PREFIX}")
print(f"POOL_SIZE: {POOL_SIZE}")
print("==================================")

# Pool de conexiones (con fallback)
try:
    cnx_pool = pooling.MySQLConnectionPool(
        pool_name="curso_pool",
        pool_size=POOL_SIZE,
        **DB_CONFIG
    )
except Exception as e:
    print(f"⚠️ No se pudo crear el pool de conexiones: {e}. Se usará conexión directa.")
    cnx_pool = None

def _get_conn():
    if cnx_pool:
        return cnx_pool.get_connection()
    return mysql.connector.connect(**DB_CONFIG)

# Cache simple en memoria (TTL 300s)
_cache = {"ts": 0.0, "data": []}
_TTL = 300.0  # 5 minutos

@curso_bp.route("/listar")
def listar_cursos():
    try:
        # Cache hit
        now = time.time()
        if _cache["data"] and now - _cache["ts"] <= _TTL:
            return jsonify(_cache["data"])

        query = f"SELECT fullname FROM {DB_PREFIX}course ORDER BY fullname"

        # Ejecutar consulta de forma segura
        with _get_conn() as conn, conn.cursor() as cursor:
            cursor.execute(query)
            cursos = [row[0] for row in cursor.fetchall()]

        # Guardar en cache
        _cache["data"] = cursos
        _cache["ts"] = now

        return jsonify(cursos)  # Siempre array

    except Exception as e:
        print("❌ Error en /listar:", e)
        traceback.print_exc()
        # Devuelvo array vacío para que el JS no falle con forEach
        return jsonify([]), 500
