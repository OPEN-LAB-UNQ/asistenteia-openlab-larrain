import os
import json
import re
import uuid
import unicodedata
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
        pass

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
@foro_bp.route("/procesar", methods=["POST"])
def procesar():
    if not check_access():   
        return jsonify({"error": "🔒 Acceso denegado"}), 403

    try:
        data = request.get_json() or {}
        pregunta = data.get("pregunta", "").strip()
        curso = data.get("curso", "").strip()
        libre = bool(data.get("libre", False))
        guardar = bool(data.get("guardar", False))
        consent_ia = bool(data.get("consentIA", False))   

        page = int(data.get("page", 1))
        size = int(data.get("size", 200))
        if page < 1:
            page = 1
        size = max(1, min(size, 1000))

        preguntas_json = cargar_preguntas()

        if "__CURSO__" in pregunta or curso:
            todas = preguntas_json.get("por_curso", []) + preguntas_json.get("por_curso_ia", [])
        else:
            todas = preguntas_json.get("generales", []) + preguntas_json.get("generales_ia", [])

        match = None
        ruta = "json_coincidencia"
        if not libre:
            match = encontrar_pregunta_similar(pregunta, todas)

        if not match:
            candidatos = buscar_semantico(pregunta, todas, top_k=5)

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

        sql_prepared, params, had_limit = _prepare_sql_and_params(
            match["sql"], curso, page, size
        )

        if not es_solo_lectura(sql_prepared):
            return jsonify({
                "status": "error",
                "message": "⚠️ Solo se permiten consultas de lectura (SELECT/WITH)."
            }), 400

        with get_conn() as conn, conn.cursor(dictionary=True) as cursor:
            cursor.execute(sql_prepared, params or None)
            resultados = cursor.fetchall()

        if match.get("descripcion"):
            if not consent_ia:
                return jsonify({
                    "status": "error",
                    "message": "⚠️ Esta consulta requiere análisis IA, pero no diste tu consentimiento."
                }), 403

            descripcion = match["descripcion"]
            # 🚀 LE PASAMOS LA CONSULTA SQL PARA QUE DETERMINE EL ORDEN CRONOLÓGICO
            respuesta_ia = procesar_pregunta_ia(descripcion, resultados, sql_prepared)

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


# === Procesar IA (MOTOR ENTERPRISE CON CRONOLOGÍA DINÁMICA) ===
def procesar_pregunta_ia(descripcion, mensajes, query_sql=""):
    if not mensajes:
        return "⚠️ No se encontraron mensajes para analizar en este curso."
        
    hilos = {}
    mapa_reemplazos = {}  
    mapa_inverso = {}     
    autores_procesados = set()

    # ALIASES GLOBALES DE APOYO
    ALIASES_BASE = {
        "matias": ["mati"],
        "matías": ["mati"],
        "camila": ["cami"],
        "profesor": ["profe", "prof"],
        "profesora": ["profe", "prof"]
    }

    # 1. ORDEN CRONOLÓGICO DINÁMICO
    if "DESC" in query_sql.upper():
        mensajes_cronologicos = list(reversed(mensajes))
    else:
        mensajes_cronologicos = list(mensajes)

    # Helpers de Normalización
    def sin_acentos(texto):
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

    def generar_variantes(texto):
        if not texto: return []
        partes = [texto] + texto.split()
        variantes = set()
        
        # Mapa simple para adivinar posibles tildes faltantes o extras
        tildes_map = {'a': 'á', 'e': 'é', 'i': 'í', 'o': 'ó', 'u': 'ú'}
        tildes_inv = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u'}
        
        for p in partes:
            p = p.strip()
            if len(p) > 2:
                variantes.add(p)
                variantes.add(sin_acentos(p))
                variantes.add(p.lower())
                variantes.add(sin_acentos(p).lower())
                
                # Agregar variantes forzando tildes por si faltan
                p_lower = p.lower()
                for sin_t, con_t in tildes_map.items():
                    if sin_t in p_lower:
                        variantes.add(p_lower.replace(sin_t, con_t))
                
                # Agregar variantes sacando tildes por si sobran
                for con_t, sin_t in tildes_inv.items():
                    if con_t in p_lower:
                        variantes.add(p_lower.replace(con_t, sin_t))
                        
        return list(variantes)
        
    def desanonimizar_respuesta(texto, mapa_inverso_local):
        resultado = texto
        for pseudo, real in mapa_inverso_local.items():
            patron = r'\b' + re.escape(pseudo) + r'\b'
            resultado = re.sub(patron, real, resultado)
        return resultado
        
    def detectar_fuga(texto, variantes_conocidas):
        texto_norm = sin_acentos(texto.lower())
        for variante in variantes_conocidas:
            if len(variante) > 3 and sin_acentos(variante.lower()) in texto_norm:
                return variante
        return None

    # 2. GENERAR MAPA DE USUARIOS CON UUID Y VARIANTES DINÁMICAS
    todas_las_variantes_generadas = set()
    for m in mensajes_cronologicos:
        firstname = m.get('firstname', '').strip()
        lastname = m.get('lastname', '').strip()
        autor_real = f"{firstname} {lastname}".strip()
        
        if autor_real and autor_real not in autores_procesados:
            pseudonimo = f"Usuario_{str(uuid.uuid4())[:6]}"
            autores_procesados.add(autor_real)
            
            variantes_usuario = generar_variantes(firstname) + generar_variantes(lastname) + generar_variantes(autor_real)
            
            fname_lower = sin_acentos(firstname.lower())
            if fname_lower in ALIASES_BASE:
                variantes_usuario.extend(ALIASES_BASE[fname_lower])
            
            for v in set(variantes_usuario):
                if v and v not in mapa_reemplazos:
                    mapa_reemplazos[v] = pseudonimo
                    todas_las_variantes_generadas.add(v)
                    
            mapa_inverso[pseudonimo] = autor_real

    claves_ordenadas = sorted(mapa_reemplazos.keys(), key=len, reverse=True)

    # 3. CONSTRUIR HILOS, LIMPIEZA HTML Y REEMPLAZO ROBUSTO
    for m in mensajes_cronologicos:
        if not m.get('message'):
            continue
            
        hilo_id = m.get('discusion_id') or m.get('tema') or 'General'
        if hilo_id not in hilos:
            hilos[hilo_id] = []
        
        autor_real = f"{m.get('firstname', '')} {m.get('lastname', '')}".strip()
        
        pseudonimo = None
        for variante in generar_variantes(autor_real):
            if variante in mapa_reemplazos:
                pseudonimo = mapa_reemplazos[variante]
                break

        if not pseudonimo:
            pseudonimo = "Usuario_Desconocido"
            
        texto_crudo = m.get('message', '').strip()
        
        # PASO 1 — LIMPIAR SÓLO HTML Y ESPACIOS MÚLTIPLES (Preservamos puntuación)
        texto = re.sub(r'<[^>]+>', ' ', texto_crudo)
        texto = re.sub(r'\s+', ' ', texto).strip()
        
        # PASO 2 — REEMPLAZO DESCENDENTE SEGURO
        for nombre_real in claves_ordenadas:
            pseudo = mapa_reemplazos[nombre_real]
            patron = r'(?i)(?<!\w)' + re.escape(nombre_real) + r'(?!\w)'
            texto = re.sub(patron, pseudo, texto)

        # ✨ ACÁ INYECTAMOS LOS DATOS FALTANTES PARA LA IA
        fecha_msg = m.get('fecha', '')
        curso_msg = m.get('curso', '')
        foro_msg = m.get('foro', '')
        
        # Armamos un bloque con la info que tengamos disponible
        meta_info = []
        if fecha_msg: meta_info.append(f"Fecha: {fecha_msg}")
        if curso_msg: meta_info.append(f"Curso: {curso_msg}")
        if foro_msg: meta_info.append(f"Foro: {foro_msg}")
        
        meta_str = f" [{ ' | '.join(meta_info) }]" if meta_info else ""
        
        hilos[hilo_id].append(f"-{meta_str} {pseudonimo}: {texto}")
        
    textos_hilos = []
    for hilo_id, msjs in hilos.items():
        textos_hilos.append(f"--- HILO DE CONVERSACIÓN: {hilo_id} (Mensajes en orden cronológico) ---\n" + "\n".join(msjs))
        
    joined = "\n\n".join(textos_hilos)

    # 4. AUDITORÍA FINAL PARA GARANTIZAR QUE NO VIAJEN NOMBRES
    fuga = detectar_fuga(joined, todas_las_variantes_generadas)
    if fuga:
        print(f"\n🚨 [ALERTA DE PRIVACIDAD] POSIBLE FUGA DETECTADA ANTES DE IA: Rastro de '{fuga}'\n")
    
    marco = _cargar_marco_etico()

    prompt = f"""
[MARCO ÉTICO]
{marco}
[FIN MARCO ÉTICO]

Sos un asistente educativo. Analizá los mensajes del foro según la siguiente consigna:

Instrucción original:
{descripcion}

IMPORTANTE: Los mensajes que vas a leer están separados por hilo y en ORDEN CRONOLÓGICO EXACTO (de más antiguo a más nuevo).
Si un mensaje más reciente tiene sentido como respuesta al contexto de un mensaje anterior (por ejemplo, alguien pregunta una fecha y otro responde "el martes"), asumí que la pregunta SÍ fue respondida, sin importar si no la citaron formalmente.
Leé la conversación como si fuera un chat.

Mensajes del foro (Anonimizados):
{joined}

Respuesta (clara y breve, como sugerencia que requiere revisión humana):
""".strip()

    # === ÚNICO PRINT LIMPIO PARA AUDITORÍA VISUAL ===
    print("\n" + "▼" * 60)
    print("👀 LO QUE VE LA IA (TEXTO EXACTO ENVIADO A OPENAI):")
    print("-" * 60)
    print(prompt)
    print("-" * 60)
    print("🏁 FIN DEL TEXTO ENVIADO A OPENAI")
    print("▲" * 60 + "\n")
    
    log_to_file("Auditoría de Prompt", prompt, "Sistema_Interno")

    # 5. ENVIAR A IA Y RECIBIR
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3
        )
        contenido = response.choices[0].message.content
        
        if not contenido or not contenido.strip():
            return "🤖 La IA no encontró evidencia relevante."
            
        # 6. DESANONIMIZAR CON REGEX SEGURO Y DEVOLVER
        respuesta_final = contenido.strip()
        respuesta_final = desanonimizar_respuesta(respuesta_final, mapa_inverso)
        return respuesta_final

    except Exception as e:
        return f"⚠️ Error al usar IA: {str(e)}"

# === Resto del archivo ===
@foro_bp.route("/")
def index():
    return render_template("foro_chat.html")

@foro_bp.route("/faq")
def faq():
    if not check_access():   
        return jsonify({"error": "🔒 Acceso denegado"}), 403
    try:
        with open("sql_base.json", "r", encoding="utf-8") as f:
            base = json.load(f)

        return jsonify({
            "generales": [p.get("pregunta", "") for p in base.get("generales", [])],
            "por_curso": [p.get("pregunta", "") for p in base.get("por_curso", [])],
            "generales_ia": [p.get("pregunta", "") for p in base.get("generales_ia", [])],
            "por_curso_ia": [p.get("pregunta", "") for p in base.get("por_curso_ia", [])]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@foro_bp.route("/chat", methods=["POST"])
def chat():
    if not check_access():   
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

        consent_ia = bool(data.get("consentIA", True))
        guardar = bool(data.get("guardar", False))

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

            if elegido.get("descripcion") and consent_ia:
                descripcion = elegido["descripcion"]
                # 🚀 LE PASAMOS LA CONSULTA SQL PARA QUE DETERMINE EL ORDEN CRONOLÓGICO
                respuesta_ia = procesar_pregunta_ia(descripcion, resultados, sql_prepared)
                
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

        preguntas_json = cargar_preguntas()
        if "__CURSO__" in mensaje or curso:
            todas = preguntas_json.get("por_curso", []) + preguntas_json.get("por_curso_ia", [])
        else:
            todas = preguntas_json.get("generales", []) + preguntas_json.get("generales_ia", [])

        match = encontrar_pregunta_similar(mensaje, todas)
        if match:
            return jsonify({"status": "sugerencias", "sugerencias": [match]})

        top_candidatos = buscar_semantico(mensaje, todas, top_k=5)

        if consent_ia and top_candidatos:
            top = rerank_con_ia(mensaje, top_candidatos)
        else:
            top = top_candidatos[:3]  

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

def buscar_semantico(mensaje, preguntas, top_k=10):
    if not preguntas or not mensaje:
        return []

    corpus = [p.get("pregunta", "") for p in preguntas if p.get("pregunta")]
    if not corpus:
        return []

    try:
        emb_corpus = modelo_embed.encode(corpus, convert_to_tensor=True)
        emb_msj = modelo_embed.encode(mensaje, convert_to_tensor=True)
        cos_scores = util.cos_sim(emb_msj, emb_corpus)[0]

        top_idx = cos_scores.topk(min(top_k, len(corpus))).indices.tolist()
        candidatos = [preguntas[i] for i in top_idx]

        return rerank_con_ia(mensaje, candidatos)

    except Exception as e:
        return []

def cargar_preguntas():
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
                pass
            except Exception as e:
                pass

    return preguntas

def encontrar_pregunta_similar(pregunta_usuario, preguntas_posibles, umbral=85):
    if not preguntas_posibles or not pregunta_usuario:
        return None
    try:
        mejores = process.extractOne(
            pregunta_usuario,
            [p.get("pregunta", "") for p in preguntas_posibles if "pregunta" in p],
            scorer=fuzz.token_sort_ratio
        )
    except Exception as e:
        return None

    if mejores and mejores[1] >= umbral:
        for p in preguntas_posibles:
            if p.get("pregunta") == mejores[0]:
                return p
    return None

def rerank_con_ia(pregunta_usuario, candidatas):
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
        return candidatas[:3]
