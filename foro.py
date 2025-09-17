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
from sentence_transformers import SentenceTransformer, util
from functools import lru_cache
import pathlib
import traceback

# Forzar carga del .env
load_dotenv(dotenv_path="/home/asistenteia/.env")

# 🔒 Clave de acceso
ACCESS_KEY = os.getenv("ACCESS_KEY", "2817")

def check_access():
    """Valida la clave enviada en el header x-pass"""
    clave = request.headers.get("x-pass")
    if clave != ACCESS_KEY:
        return False
    return True

# Cargar modelo global al inicio (una sola vez)
modelo_embed = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# --- Marco ético ---
@lru_cache(maxsize=1)
def _cargar_marco_etico(max_chars: int = 1800) -> str:
    for p in (
        pathlib.Path("MARCO_ETICO.txt"),
        pathlib.Path(__file__).parent / "MARCO_ETICO.txt",
        pathlib.Path(__file__).parent.parent / "MARCO_ETICO.txt",
    ):
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")[:max_chars].strip()
            except Exception:
                pass
    return ("Principios: supervisión humana (la IA asiste, no decide), proporcionalidad, "
            "equidad/no discriminación, transparencia/explicabilidad, privacidad y seguridad. "
            "Respuestas como sugerencia y con revisión humana.")

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

# Pool de conexiones
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
try:
    cnx_pool = pooling.MySQLConnectionPool(
        pool_name="foro_pool",
        pool_size=POOL_SIZE,
        **DB_CONFIG
    )
except Exception:
    cnx_pool = None

def get_conn():
    if cnx_pool:
        return cnx_pool.get_connection()
    return mysql.connector.connect(**DB_CONFIG)

SQL_JSON_PATH = os.path.join(os.path.dirname(__file__), "sql_base.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "interacciones.log")

MODULO_TRAD = {"forum": "Foro", "assign": "Tarea", "resource": "Archivo", "quiz": "Cuestionario"}
TRADUCCION_COLUMNAS = {
    "firstname": "Nombre", "lastname": "Apellido", "message": "Mensaje",
    "fecha": "Fecha", "finalgrade": "Nota", "promedio": "Promedio",
    "fullname": "Curso", "ultima_conexion": "Última conexión",
    "primera_conexion": "Primera conexión", "accesos": "Cantidad de accesos",
    "tipo_recurso": "Tipo de recurso", "cantidad": "Cantidad",
    "duedate": "Fecha de Finalización"
}

ia_cache = TTLCache(maxsize=100, ttl=3600)

# === Seguridad SQL ===
LEER_REGEX = re.compile(r'^\s*(SELECT|WITH)\b', re.IGNORECASE)
def es_solo_lectura(sql: str) -> bool:
    if not sql:
        return False
    partes = [p.strip() for p in sql.split(';') if p.strip()]
    return bool(partes) and all(LEER_REGEX.match(sent) for sent in partes)

# === Logs ===
def log_to_file(pregunta, respuesta, curso):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] Curso: {curso}\n")
            f.write(f"Pregunta: {pregunta}\n")
            f.write(f"Respuesta: {respuesta}\n")
            f.write("=" * 80 + "\n")
    except Exception as e:
        print(f"⚠️ Error al escribir log: {e}")

# === Serialización de resultados ===
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

# === Preparar SQL ===
def _prepare_sql_and_params(sql_raw: str, curso: str, page: int, size: int):
    if not sql_raw:
        return "", [], False
    sql = sql_raw.replace("{PREFIX}", DB_PREFIX).strip()
    params = []
    sql, n1 = re.subn(r"(['\"])__CURSO__\1", "%s", sql)
    sql, n2 = re.subn(r"\b__CURSO__\b", "%s", sql)
    apariciones = n1 + n2
    if apariciones > 0 and curso:
        params.extend([curso] * apariciones)

    def _map_course_eq_placeholder(m):
        left = m.group(1)
        return f"{left}(SELECT id FROM {DB_PREFIX}course WHERE fullname = %s LIMIT 1)"

    if curso and "%s" in sql:
        sql = re.sub(r"(\b(?:\w+\.)?course\s*=\s*)%s\b",
                     _map_course_eq_placeholder, sql, flags=re.IGNORECASE)

    has_limit = bool(re.search(r"\blimit\s+\d+", sql, flags=re.IGNORECASE))
    if not has_limit:
        sql = sql.rstrip(";") + " LIMIT %s OFFSET %s"
        params.extend([size, (page - 1) * size])
    return sql, params, has_limit

# === Rutas ===
# === Ruta /procesar ===
@foro_bp.route("/procesar", methods=["POST"])
def procesar():
    if not check_access():   # 🔒 validación de clave antes de todo
        return jsonify({"error": "🔒 Acceso denegado"}), 403

    try:
        data = request.get_json() or {}
        pregunta = data.get("pregunta", "").strip()
        curso = data.get("curso", "").strip()
        libre = bool(data.get("libre", False))
        guardar = bool(data.get("guardar", False))
        consent_ia = bool(data.get("consentIA", False))   # 👈 por defecto False

        # Paginación
        page = int(data.get("page", 1))
        size = int(data.get("size", 200))
        if page < 1:
            page = 1
        size = max(1, min(size, 1000))

        print(f"📥 Pregunta recibida: {pregunta} | curso={curso} | libre={libre} | guardar={guardar} | consentIA={consent_ia}")

        # 1) Cargar preguntas
        preguntas_json = cargar_preguntas()

        # 🔎 Detectar si es consulta general o por curso
        if "__CURSO__" in pregunta or curso:
            todas = preguntas_json.get("por_curso", []) + preguntas_json.get("por_curso_ia", [])
        else:
            todas = preguntas_json.get("generales", []) + preguntas_json.get("generales_ia", [])

        # 2) Buscar match literal
        match = None
        ruta = "json_coincidencia"
        if not libre:
            match = encontrar_pregunta_similar(pregunta, todas)

        # 3) Si no hay match → usar esquema semántico
        if not match:
            candidatos = buscar_semantico(pregunta, todas, top_k=5)

            # ⚖️ Solo reordena con IA si hay consentimiento
            if consent_ia:
                top = rerank_con_ia(pregunta, candidatos)
            else:
                top = candidatos

            if top:
                mejor = top[0]
                if not mejor.get("score"):
                    mejor["score"] = fuzz.ratio(pregunta.lower(), mejor["pregunta"].lower())

                if mejor["score"] >= 90:
                    match = mejor
                    ruta = "json_semantico_auto"
                else:
                    return jsonify({
                        "status": "sugerencias",
                        "sugerencias": [
                            {
                                "pregunta": p["pregunta"],
                                "sql": p["sql"],
                                "explicacion": p.get("explicacion"),
                                "descripcion": p.get("descripcion"),
                                "score": p.get("score", "")
                            }
                            for p in top
                        ]
                    })
            else:
                return jsonify({
                    "status": "error",
                    "message": "⚠️ No se encontró una consulta predefinida ni sugerencias semánticas."
                }), 400

        # 4) Preparar SQL
        sql_prepared, params, had_limit = _prepare_sql_and_params(
            match["sql"], curso, page, size
        )

        # 5) Verificar seguridad
        if not es_solo_lectura(sql_prepared):
            return jsonify({
                "status": "error",
                "message": "⚠️ Solo se permiten consultas de lectura (SELECT/WITH)."
            }), 400

        # 6) Ejecutar
        with get_conn() as conn, conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql_prepared, params or None)
            resultados = cursor.fetchall()

        # 7) Si la pregunta requiere IA
        if match.get("descripcion"):
            if not consent_ia:
                # ❌ No hay consentimiento → no responder nada
                return jsonify({
                    "status": "error",
                    "message": "⚠️ Esta consulta requiere análisis IA, pero no diste tu consentimiento."
                }), 403

            descripcion = match["descripcion"]
            respuesta_ia = procesar_pregunta_ia(descripcion, resultados)

            if guardar:
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
                "has_more": (len(resultados) == size) and (not had_limit)
            })

        # 8) Caso normal (sin IA)
        data_final = serializar_resultado(resultados)

        if guardar:
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



# === Procesar IA ===
def procesar_pregunta_ia(descripcion, mensajes):
    if not mensajes:
        return "⚠️ No se encontraron mensajes para analizar en este curso."

    joined = "\n\n".join([
        f"{m.get('firstname','')} {m.get('lastname','')}: {m.get('message','')}"
        for m in mensajes if m.get('message')
    ])
    marco = _cargar_marco_etico()

    prompt = f"""
[MARCO ÉTICO]
{marco}
[FIN MARCO ÉTICO]

Sos un asistente educativo. Analizá los mensajes del foro según la siguiente consigna:

Instrucción:
{descripcion}

Mensajes:
{joined}

Respuesta (clara y breve, como sugerencia que requiere revisión humana):
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


# === Rutas básicas ===
@foro_bp.route("/")
def index():
    return render_template("foro_chat.html")


@foro_bp.route("/faq")
def faq():
    if not check_access():   # 🔒 validación de clave
        return jsonify({"error": "🔒 Acceso denegado"}), 403
    try:
        # Cargar SOLO desde sql_base.json (no ejemplos)
        with open("sql_base.json", "r", encoding="utf-8") as f:
            base = json.load(f)

        return jsonify({
            "generales": [p.get("pregunta", "") for p in base.get("generales", [])],
            "por_curso": [p.get("pregunta", "") for p in base.get("por_curso", [])],
            "generales_ia": [p.get("pregunta", "") for p in base.get("generales_ia", [])],
            "por_curso_ia": [p.get("pregunta", "") for p in base.get("por_curso_ia", [])]
        })
    except Exception as e:
        print(f"⚠️ Error en /faq: {e}")
        return jsonify({"error": str(e)}), 500

# === Ruta /chat ===
@foro_bp.route("/chat", methods=["POST"])
def chat():
    if not check_access():   # 🔒 validación de clave
        return jsonify({"error": "🔒 Acceso denegado"}), 403
    try:
        data = request.get_json() or {}
        mensaje = data.get("mensaje", "").strip()
        seleccion = data.get("seleccion")
        sugerencias = data.get("sugerencias", [])
        curso = data.get("curso", "").strip()
        page = int(data.get("page", 1))
        size = int(data.get("size", 100))
        if page < 1: 
            page = 1
        size = max(1, min(size, 1000))

        # 🚩 Consentimiento IA y guardado
        consent_ia = bool(data.get("consentIA", True))
        guardar = bool(data.get("guardar", False))

        # ✅ Caso 1: selección explícita de sugerencia
        if seleccion is not None and sugerencias:
            idx = int(seleccion) - 1
            if idx < 0 or idx >= len(sugerencias):
                return jsonify({"status": "error", "message": "Selección inválida"}), 400

            elegido = sugerencias[idx]
            sql_raw = elegido.get("sql", "")
            sql_raw = "\n".join(
                [line for line in sql_raw.splitlines() if not line.strip().startswith("--")]
            ).strip()

            if not es_solo_lectura(sql_raw):
                return jsonify({"status": "error", "message": "Consulta no permitida"}), 400

            sql_prepared, params, had_limit = _prepare_sql_and_params(sql_raw, curso, page, size)
            with get_conn() as conn, conn.cursor(dictionary=True) as cursor:
                cursor.execute(sql_prepared, params or None)
                resultados = cursor.fetchall()

            # 🔎 IA solo si hay descripción y consentimiento
            if elegido.get("descripcion") and consent_ia:
                descripcion = elegido["descripcion"]
                respuesta_ia = procesar_pregunta_ia(descripcion, resultados)
                if guardar:
                    log_to_file(f"Selección {seleccion}", f"SQL (IA): {sql_prepared}", curso)

                return jsonify({
                    "status": "ok",
                    "ia": True,
                    "respuesta": [{"Análisis IA": respuesta_ia}],
                    "query": sql_prepared,
                    "params": params,
                    "page": page,
                    "size": size,
                    "count": len(resultados),
                    "has_more": (len(resultados) == size) and (not had_limit)
                })

            # 🟢 Caso normal
            data_final = serializar_resultado(resultados)
            if guardar:
                log_to_file(f"Selección {seleccion}", f"SQL: {sql_prepared}", curso)

            return jsonify({
                "status": "ok",
                "ia": False,
                "respuesta": data_final,
                "query": sql_prepared,
                "params": params,
                "page": page,
                "size": size,
                "count": len(resultados),
                "has_more": (len(resultados) == size) and (not had_limit)
            })

        # ✅ Caso 2: texto libre → buscar coincidencias
        preguntas_json = cargar_preguntas()
        if "__CURSO__" in mensaje or curso:
            todas = preguntas_json.get("por_curso", []) + preguntas_json.get("por_curso_ia", [])
        else:
            todas = preguntas_json.get("generales", []) + preguntas_json.get("generales_ia", [])

        # Paso 1: coincidencia literal
        match = encontrar_pregunta_similar(mensaje, todas)
        if match:
            return jsonify({"status": "sugerencias", "sugerencias": [match]})

        # Paso 2: embeddings
        top_candidatos = buscar_semantico(mensaje, todas, top_k=5)

        # Paso 3: rerank con IA (si hay consentimiento)
        if consent_ia and top_candidatos:
            top = rerank_con_ia(mensaje, top_candidatos)
        else:
            top = top_candidatos[:3]  # fallback simple sin IA

        return jsonify({
            "status": "sugerencias",
            "sugerencias": [
                {
                    "pregunta": p.get("pregunta"),
                    "sql": p.get("sql"),
                    "explicacion": p.get("explicacion") or None,
                    "descripcion": p.get("descripcion") or None
                }
                for p in top
            ]
        })

    except Exception as e:
        print(f"❌ Error en /foro/chat: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



# === Similitud semántica con embeddings ===
# === Similitud semántica con embeddings + IA ===
def buscar_semantico(mensaje, preguntas, top_k=10):
    """
    Busca coincidencias con embeddings y luego aplica IA
    para priorizar el sentido profundo.
    """
    if not preguntas or not mensaje:
        return []

    # Prepara el corpus de preguntas
    corpus = [p.get("pregunta", "") for p in preguntas if p.get("pregunta")]
    if not corpus:
        return []

    try:
        # Embeddings iniciales para acotar candidatos
        emb_corpus = modelo_embed.encode(corpus, convert_to_tensor=True)
        emb_msj = modelo_embed.encode(mensaje, convert_to_tensor=True)
        cos_scores = util.cos_sim(emb_msj, emb_corpus)[0]

        # Selecciona top_k candidatos más cercanos
        top_idx = cos_scores.topk(min(top_k, len(corpus))).indices.tolist()
        candidatos = [preguntas[i] for i in top_idx]

        # Reordenamiento conceptual con IA
        return rerank_con_ia(mensaje, candidatos)

    except Exception as e:
        print(f"⚠️ Error en embeddings: {e}")
        return []



# === Preguntas ===
def cargar_preguntas():
    """
    Carga y combina preguntas desde sql_base.json y sql_ejemplos.json.
    Devuelve siempre un diccionario con las 4 claves esperadas:
    - generales
    - por_curso
    - generales_ia
    - por_curso_ia
    """
    base_path = os.path.dirname(__file__)
    archivos = [
        os.path.join(base_path, "sql_base.json"),
        os.path.join(base_path, "sql_ejemplos.json"),
    ]

    preguntas = {
        "generales": [],
        "por_curso": [],
        "generales_ia": [],
        "por_curso_ia": []
    }

    for archivo in archivos:
        if os.path.exists(archivo):
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for clave in preguntas.keys():
                            if clave in data and isinstance(data[clave], list):
                                preguntas[clave].extend(data[clave])
            except json.JSONDecodeError:
                print(f"⚠️ Error: {archivo} no es un JSON válido")
            except Exception as e:
                print(f"⚠️ Error cargando {archivo}: {e}")

    return preguntas


# === Coincidencia literal con RapidFuzz ===
def encontrar_pregunta_similar(pregunta_usuario, preguntas_posibles, umbral=85):
    """
    Busca coincidencia literal aproximada usando RapidFuzz.
    Devuelve la pregunta si supera el umbral, o None si no hay match.
    """
    if not preguntas_posibles or not pregunta_usuario:
        return None
    try:
        mejores = process.extractOne(
            pregunta_usuario,
            [p.get("pregunta", "") for p in preguntas_posibles if "pregunta" in p],
            scorer=fuzz.token_sort_ratio
        )
    except Exception as e:
        print(f"⚠️ Error en RapidFuzz: {e}")
        return None

    if mejores and mejores[1] >= umbral:
        for p in preguntas_posibles:
            if p.get("pregunta") == mejores[0]:
                return p
    return None


# === Coincidencia semántica con IA (mejorada) ===
def rerank_con_ia(pregunta_usuario, candidatas):
    """
    Usa IA (gpt-4o-mini) para analizar el sentido profundo
    y devolver las opciones más cercanas en intención/semántica.
    """
    if not candidatas or not pregunta_usuario:
        return []

    opciones = "\n".join([
        f"{i+1}) {c.get('pregunta','')}"
        + (f"\n   Explicación: {c.get('explicacion')}" if c.get('explicacion') else "")
        + (f"\n   Descripción: {c.get('descripcion')}" if c.get('descripcion') else "")
        for i, c in enumerate(candidatas)
    ])

    prompt = f"""
El usuario preguntó: "{pregunta_usuario}"

Opciones de preguntas disponibles:
{opciones}

Instrucciones para vos (IA):
- No te limites a palabras exactas.
- Analizá el SENTIDO PROFUNDO o el TEMA central de la pregunta del usuario.
- Ejemplo: si el usuario pregunta por "emociones", también son válidas
  preguntas sobre tristeza, alegría, ansiedad, sentimientos o estados de ánimo.
- Podés devolver entre 1 y 5 opciones relacionadas en intención.
- No inventes nuevas preguntas, solo elegí de la lista.
- Si realmente ninguna tiene relación conceptual, devolvé "ninguna".
- Responde SOLO con los números separados por coma (ej: "1,3,4").
"""

    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0
        )
        contenido = (resp.choices[0].message.content or "").strip().lower()

        if not contenido or contenido in ["0", "ninguna", "n/a"]:
            return []

        idxs = [int(x)-1 for x in contenido.split(",") if x.strip().isdigit()]
        return [candidatas[i] for i in idxs if 0 <= i < len(candidatas)]

    except Exception as e:
        print("⚠️ Error en rerank con IA:", e)
        # fallback → devolvemos los 3 primeros candidatos
        return candidatas[:3]