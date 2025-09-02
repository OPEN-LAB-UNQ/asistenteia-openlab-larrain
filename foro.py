import os
import json
import re
import mysql.connector
from mysql.connector import pooling
from flask import Blueprint, request, jsonify, render_template
from dotenv import load_dotenv
from datetime import datetime
from decimal import Decimal
from openai import OpenAI
from rapidfuzz import fuzz, process
from cachetools import TTLCache

# Forzar la carga del .env desde la ruta absoluta
load_dotenv(dotenv_path="/home/asistenteia/.env")

foro_bp = Blueprint("foro", __name__)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DB_PREFIX = os.getenv("DB_PREFIX")
if not DB_PREFIX:
    raise ValueError("⚠️ Debes definir DB_PREFIX en el archivo .env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT", 3306))
}

# Pool de conexiones para eficiencia y estabilidad
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
try:
    cnx_pool = pooling.MySQLConnectionPool(
        pool_name="foro_pool",
        pool_size=POOL_SIZE,
        **DB_CONFIG
    )
except Exception:
    # Fallback: si falla el pool, seguimos con connect normal (no rompe la app)
    cnx_pool = None

def get_conn():
    if cnx_pool:
        return cnx_pool.get_connection()
    return mysql.connector.connect(**DB_CONFIG)

# Log para verificar que se cargó el .env correctamente
print("=== Configuración cargada desde .env (foro.py) ===")
for k, v in DB_CONFIG.items():
    if k != "password":
        print(f"{k}: {v}")
print(f"DB_PREFIX: {DB_PREFIX}")
print(f"POOL_SIZE: {POOL_SIZE}")
print("==============================================")

SQL_JSON_PATH = os.path.join(os.path.dirname(__file__), "sql_base.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "interacciones.log")

MODULO_TRAD = {
    "forum": "Foro", "assign": "Tarea",
    "resource": "Archivo", "quiz": "Cuestionario"
}

TRADUCCION_COLUMNAS = {
    "firstname": "Nombre", "lastname": "Apellido", "message": "Mensaje",
    "fecha": "Fecha", "finalgrade": "Nota", "promedio": "Promedio",
    "fullname": "Curso", "ultima_conexion": "Última conexión",
    "primera_conexion": "Primera conexión", "accesos": "Cantidad de accesos",
    "tipo_recurso": "Tipo de recurso", "cantidad": "Cantidad",
    "duedate": "Fecha de Finalización"
}

ia_cache = TTLCache(maxsize=100, ttl=3600)

# === Permitir lecturas libres (SELECT/WITH) y bloquear lo demás ===
LEER_REGEX = re.compile(r'^\s*(SELECT|WITH)\b', re.IGNORECASE)

def es_solo_lectura(sql: str) -> bool:
    """
    True si TODAS las sentencias son SELECT/WITH.
    No agrega LIMITs: lecturas pasan tal cual.
    """
    if not sql:
        return False
    partes = [p.strip() for p in sql.split(';') if p.strip()]
    return bool(partes) and all(LEER_REGEX.match(sent) for sent in partes)

def log_to_file(pregunta, respuesta, curso):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Curso: {curso}\n")
            f.write(f"Pregunta: {pregunta}\n")
            f.write(f"Respuesta: {respuesta}\n")
            f.write("=" * 80 + "\n")
    except Exception as e:
        print(f"⚠️ Error al escribir log: {e}")

def serializar_resultado(data):
    resultado = []
    for fila in data:
        nueva = {}
        for k, v in fila.items():
            key = "cantidad" if isinstance(k, str) and "count" in k.lower() else k
            if isinstance(v, Decimal):
                v = float(v)
            if isinstance(v, (int, float)) and isinstance(key, str) and any(
                t in key.lower() for t in ["fecha", "time", "conexion", "due", "duedate", "created"]
            ):
                try:
                    v = datetime.fromtimestamp(v).strftime("%d/%m/%Y %H:%M")
                except Exception:
                    pass
            elif isinstance(v, datetime):
                v = v.strftime("%d/%m/%Y %H:%M")
            key_esp = TRADUCCION_COLUMNAS.get(key, key)
            if key_esp == "Tipo de recurso":
                v = MODULO_TRAD.get(str(v).lower(), v)
            nueva[key_esp] = v
        resultado.append(nueva)
    return resultado

def _prepare_sql_and_params(sql_raw: str, curso: str, page: int, size: int):
    """
    - Reemplaza {PREFIX} por DB_PREFIX
    - Sustituye '__CURSO__' por placeholder %s y agrega el valor a params
    - Si se usa '... <alias>.course = __CURSO__', mapea a id con subselect por fullname
    - Si no hay LIMIT, agrega 'LIMIT %s OFFSET %s' y añade size/offset a params
    """
    if not sql_raw:
        return "", [], False

    # 1) Prefix seguro
    sql = sql_raw.replace("{PREFIX}", DB_PREFIX).strip()

    # 2) Parametrización de curso (si aparece en la SQL)
    params = []
    # Reemplazo con y sin comillas: '__CURSO__' o __CURSO__
    sql, n1 = re.subn(r"(['\"])__CURSO__\1", "%s", sql)
    sql, n2 = re.subn(r"\b__CURSO__\b", "%s", sql)
    apariciones = n1 + n2
    if apariciones > 0 and curso:
        # agregamos el valor del curso tantas veces como haya placeholders
        params.extend([curso] * apariciones)

    # 2b) Mapeo automático para '... <alias>.course = %s' (columna INT) usando fullname
    # Ej.: "a.course = %s" -> "a.course = (SELECT id FROM <prefix>course WHERE fullname = %s LIMIT 1)"
    def _map_course_eq_placeholder(m):
        left = m.group(1)  # ej. "a.course = "
        return f"{left}(SELECT id FROM {DB_PREFIX}course WHERE fullname = %s LIMIT 1)"

    if curso and "%s" in sql:
        sql = re.sub(r"(\b(?:\w+\.)?course\s*=\s*)%s\b", _map_course_eq_placeholder, sql, flags=re.IGNORECASE)

    # 3) Paginación automática si no hay LIMIT explícito
    has_limit = bool(re.search(r"\blimit\s+\d+", sql, flags=re.IGNORECASE))
    if not has_limit:
        sql = sql.rstrip(";")
        sql += " LIMIT %s OFFSET %s"
        params.extend([size, (page - 1) * size])

    return sql, params, has_limit

def procesar_pregunta_ia(descripcion, mensajes):
    if not mensajes:
        return "⚠️ No se encontraron mensajes para analizar en este curso."

    joined = "\n\n".join([
        f"{m.get('firstname', '')} {m.get('lastname', '')}: {m.get('message', '')}"
        for m in mensajes if m.get('message')
    ])

    prompt = f"""
Sos un asistente educativo. Analizá los mensajes del foro según la siguiente consigna:

Instrucción:
{descripcion}

Mensajes:
{joined}

Respuesta:
""".strip()
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3
        )
        contenido = response.choices[0].message.content
        return contenido.strip() if contenido and contenido.strip() else "🤖 La IA no encontró evidencia relevante."
    except Exception as e:
        return f"⚠️ Error al usar IA: {str(e)}"

def cargar_preguntas():
    with open(SQL_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def encontrar_pregunta_similar(pregunta_usuario, preguntas_posibles, umbral=85):
    if not preguntas_posibles:
        return None
    try:
        mejores = process.extractOne(
            pregunta_usuario,
            [p["pregunta"] for p in preguntas_posibles],
            scorer=fuzz.token_sort_ratio
        )
    except Exception:
        return None
    if mejores and mejores[1] >= umbral:
        for p in preguntas_posibles:
            if p["pregunta"] == mejores[0]:
                return p
    return None

@foro_bp.route("/")
def index():
    return render_template("foro_chat.html")

@foro_bp.route("/faq")
def faq():
    try:
        preguntas = cargar_preguntas()
        return jsonify({
            "generales": [p["pregunta"] for p in preguntas.get("generales", []) + preguntas.get("generales_ia", [])],
            "por_curso": [p["pregunta"] for p in preguntas.get("por_curso", []) + preguntas.get("por_curso_ia", [])]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@foro_bp.route("/procesar", methods=["POST"])
def procesar():
    try:
        data = request.get_json() or {}
        pregunta = data.get("pregunta", "").strip()
        curso = data.get("curso", "").strip()
        mensajes = data.get("mensajes", [])
        libre = bool(data.get("libre", False))  # ✅ modo libre desde el front

        # Paginación (opcional desde el front)
        page = int(data.get("page", 1))
        size = int(data.get("size", 200))
        if page < 1: page = 1
        size = max(1, min(size, 1000))  # cap razonable

        print(f"📥 Pregunta recibida: {pregunta}")
        print(f"📚 Curso recibido: {curso} | modoLibre={libre} | page={page} size={size}")

        # 1) Intento rápido: preguntas estructuradas del JSON (solo si NO es libre)
        preguntas_json = cargar_preguntas()
        todas = preguntas_json.get("generales", []) + preguntas_json.get("por_curso", []) + \
                preguntas_json.get("generales_ia", []) + preguntas_json.get("por_curso_ia", [])

        match = None
        ruta = "json_coincidencia"
        if not libre:
            match = encontrar_pregunta_similar(pregunta, todas)

        # 2) Si no hay match textual o es libre, pasamos al motor de intención (helper/IA)
        if not match:
            ruta = "intencion"
            from intencion import buscar_intencion
            intencion = buscar_intencion(pregunta, curso)  # maneja ES/EN y helper de patrones
            sql = (intencion or {}).get("sql", "") or ""
            explicacion = (intencion or {}).get("explicacion", "")
            print(f"🧠 Camino intención: {explicacion}")
            print(f"🧠 SQL propuesta: {sql}")

            if not es_solo_lectura(sql):
                return jsonify({
                    "status": "error",
                    "message": "⚠️ No se pudo generar una consulta de lectura para esa pregunta."
                }), 400

            match = {
                "pregunta": (intencion or {}).get("pregunta_match", "SQL generada por IA"),
                "sql": sql,
                "explicacion": explicacion
            }
            sql_prepared, params, had_limit = _prepare_sql_and_params(match["sql"], curso, page, size)

        else:
            # Coincidencia exacta del JSON
            # No interpolamos strings: parametrizamos '__CURSO__' y dejamos LIMIT/OFFSET si falta
            sql_prepared, params, had_limit = _prepare_sql_and_params(match["sql"], curso, page, size)

        # Última verificación de solo lectura (por si quedó algo raro tras el preprocesado)
        if not es_solo_lectura(sql_prepared):
            return jsonify({
                "status": "error",
                "message": "⚠️ Solo se permiten consultas de lectura (SELECT/WITH)."
            }), 400

        # 3) Ejecutar SQL de manera segura (parametrizada)
        with get_conn() as conn, conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql_prepared, params or None)
            resultados = cursor.fetchall()

        # 4) Rama de “Análisis IA” si la pregunta estructurada es del tipo IA (descripcion)
        if "descripcion" in (match or {}):
            descripcion = match["descripcion"]
            respuesta_ia = procesar_pregunta_ia(descripcion, resultados)
            if data.get("guardar", False):
                log_to_file(pregunta, str(respuesta_ia), curso)
            return jsonify({
                "status": "ok",
                "ia": True,
                "ruta": ruta,
                "explicacion": match.get("explicacion", ""),
                "respuesta": [{"Análisis IA": respuesta_ia}],
                "query": sql_prepared,
                "params": params,
                "page": page,
                "size": size,
                "count": len(resultados),
                "has_more": (len(resultados) == size) and (not had_limit)  # hay más si alcanzó el tope agregado
            })

        # 5) Serializar y devolver
        data_final = serializar_resultado(resultados)
        if data.get("guardar", False):
            log_to_file(pregunta, str(data_final), curso)

        return jsonify({
            "status": "ok",
            "ia": False,
            "ruta": ruta,
            "explicacion": match.get("explicacion", ""),
            "respuesta": data_final,
            "query": sql_prepared,
            "params": params,
            "page": page,
            "size": size,
            "count": len(resultados),
            "has_more": (len(resultados) == size) and (not had_limit)
        })

    except Exception as e:
        print(f"❌ Error procesando: {e}")
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500
