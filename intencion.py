import os
import json
import re
import pathlib
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
from openai import OpenAI

# ===============================
# Cargar configuración desde .env
# ===============================
load_dotenv(dotenv_path="/home/asistenteia/.env")

DB_PREFIX = os.getenv("DB_PREFIX")
if not DB_PREFIX:
    raise ValueError("⚠️ Debes definir DB_PREFIX en el archivo .env")

# ==============
# CLIENTE OPENAI
# ==============
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==============
# MODELO IA local
# ==============
modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# =====================
# Cargar preguntas SQL
# =====================
with open("sql_base.json", "r", encoding="utf-8") as f:
    base_json = json.load(f)

# Unificar todas las preguntas con SQL asociada
base = []
for grupo in ["generales", "generales_ia", "por_curso", "por_curso_ia"]:
    for p in base_json.get(grupo, []):
        if "sql" in p:
            base.append(p)

# Embeddings para búsqueda semántica en JSON
preguntas_base = [p["pregunta"] for p in base]
embeddings_base = modelo.encode(preguntas_base, convert_to_tensor=True) if preguntas_base else None

# -------------------------
# Utilidades SQL / limpieza
# -------------------------
_LEER_RE = re.compile(r'^\s*(SELECT|WITH)\b', re.IGNORECASE)

def es_solo_lectura(sql: str) -> bool:
    if not sql:
        return False
    partes = [p.strip() for p in sql.split(";") if p.strip()]
    return bool(partes) and all(_LEER_RE.match(s) for s in partes)

def limpiar_salida_sql(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    # quitar fences
    s = re.sub(r"^```(\w+)?\s*|\s*```$", "", s, flags=re.DOTALL)
    # quedarnos desde SELECT/WITH
    m = re.search(r'((SELECT|WITH)\b[\s\S]+)$', s, flags=re.IGNORECASE)
    s = m.group(1).strip() if m else s
    # quitar comentarios en línea
    s = "\n".join(ln for ln in s.splitlines() if not re.match(r'^\s*(--|#)', ln))
    return s.strip()

# ---------------------------------------
# Carga y selección de ejemplos desde TXT
# ---------------------------------------
TXT_PATHS = [
    pathlib.Path(__file__).parent / "sql_ejemplos.txt",
    pathlib.Path("sql_ejemplos.txt"),
]

def _cargar_ejemplos_txt():
    """Devuelve lista de dicts: [{'q': str, 'sql': str}]"""
    contenido = ""
    for p in TXT_PATHS:
        if p.exists():
            contenido = p.read_text(encoding="utf-8")
            break
    if not contenido:
        return []

    ejemplos = []

    # Formato A: bloques 'Pregunta:' ... 'SQL:' (separados por --- opcional)
    bloques = re.split(r'\n-{3,}\n', contenido.strip())
    for b in bloques:
        m_q = re.search(r'(?im)^pregunta:\s*(.+)$', b)
        m_s = re.search(r'(?is)^sql:\s*(.+)$', b)
        if m_q and m_s:
            sql = m_s.group(1).strip()
            if es_solo_lectura(sql):
                ejemplos.append({"q": m_q.group(1).strip(), "sql": sql})

    # Formato B: '-- PREGUNTA:' seguido de una SQL
    partes = re.split(r'(?im)^\s*--\s*pregunta:\s*', contenido)
    for chunk in partes[1:]:
        lineas = chunk.splitlines()
        q = (lineas[0] if lineas else "").strip()
        sql = "\n".join(lineas[1:]).strip()
        sql = re.split(r'(?im)^\s*--\s*pregunta:\s*', sql)[0].strip()
        if q and es_solo_lectura(sql):
            ejemplos.append({"q": q, "sql": sql})

    # Dedupe
    vistos, unicos = set(), []
    for ej in ejemplos:
        clave = (ej["q"], ej["sql"])
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(ej)
    return unicos

_EJEMPLOS_TXT = _cargar_ejemplos_txt()

def _few_shots_desde_txt(pregunta: str, k: int = 3):
    """Elige hasta k ejemplos del txt más parecidos a la pregunta."""
    if not _EJEMPLOS_TXT:
        return []
    corpus = [e["q"] for e in _EJEMPLOS_TXT]
    q_emb = modelo.encode(pregunta, convert_to_tensor=True)
    c_emb = modelo.encode(corpus, convert_to_tensor=True)
    sims = util.cos_sim(q_emb, c_emb)[0]
    top_idx = sims.topk(k=min(k, len(corpus))).indices.tolist()
    return [_EJEMPLOS_TXT[i] for i in top_idx]

# ===================================
# Prompt y Generación con GPT (fallback)
# ===================================
def _prompt_sql(pregunta: str, curso: str, fewshots: list, reforzado: bool = False):
    # Importante: NO interpolar curso ni prefix. Usar {PREFIX} y __CURSO__ literal.
    reglas = (
        "Devolvé SOLO una consulta SQL de lectura (SELECT o WITH). "
        "NO incluyas explicaciones ni bloques de código. "
        "Usá {PREFIX} como prefijo literal de tablas (no lo reemplaces). "
        "Si hay que filtrar por curso, usá el literal __CURSO__ sin comillas en la condición, por ejemplo: "
        "WHERE c.fullname = __CURSO__ "
        "(el backend parametrizará y pondrá las comillas). "
        "No agregues LIMIT a menos que la pregunta lo pida explícitamente."
    )
    if reforzado:
        reglas += " La respuesta DEBE empezar con SELECT o WITH y contener únicamente SQL."

    mensajes = [
        {"role": "system", "content": "Sos un generador de SQL para Moodle. Respondé solo con la SQL."},
        {"role": "user", "content": f"Reglas: {reglas}"},
    ]

    # Few-shots provenientes del TXT
    for ej in fewshots:
        mensajes.append({"role": "user", "content": ej["q"]})
        # Normalizamos ejemplos: garantizar {PREFIX} y __CURSO__ sin interpolar
        sql_ej = ej["sql"]
        sql_ej = re.sub(rf"\b{re.escape(DB_PREFIX)}", "{PREFIX}", sql_ej)
        sql_ej = sql_ej.replace("'__CURSO__'", "__CURSO__")
        mensajes.append({"role": "assistant", "content": sql_ej})

    # Tablas útiles (como referencia para el modelo)
    tablas = (
        f"- {{PREFIX}}course (id, fullname)\n"
        f"- {{PREFIX}}user (id, firstname, lastname)\n"
        f"- {{PREFIX}}forum (id, course, name)\n"
        f"- {{PREFIX}}forum_posts (id, discussion, message, userid, created)\n"
        f"- {{PREFIX}}grade_items (id, courseid)\n"
        f"- {{PREFIX}}grade_grades (id, userid, itemid, finalgrade)\n"
        f"- {{PREFIX}}quiz (id, course, name)\n"
        f"- {{PREFIX}}quiz_attempts (id, quiz, userid)\n"
        f"- {{PREFIX}}assign (id, course, name, duedate)\n"
        f"- {{PREFIX}}logstore_standard_log (id, userid, courseid, timecreated)\n"
    )
    mensajes.append({"role": "user", "content": f"Tablas disponibles:\n{tablas}"})
    mensajes.append({"role": "user", "content": f"Pregunta:\n{pregunta}\nCurso activo: \"{curso or ''}\""})
    return mensajes

def generar_sql_con_gpt(pregunta, curso):
    shots = _few_shots_desde_txt(pregunta, k=3)
    for intento in (1, 2):  # intento normal + reforzado
        msgs = _prompt_sql(pregunta, curso, shots, reforzado=(intento == 2))
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=msgs,
                temperature=0,
                max_tokens=300
            )
            sql_raw = resp.choices[0].message.content
            sql = limpiar_salida_sql(sql_raw)
            if es_solo_lectura(sql):
                # NO reemplazamos {PREFIX} ni __CURSO__; eso lo hace el backend
                return sql
        except Exception as e:
            print(f"❌ Error generando SQL con GPT (intento {intento}): {e}")
    return ""

# ===================================
# Función principal
# ===================================
def buscar_intencion(pregunta_usuario, curso=""):
    pregunta_original = pregunta_usuario.strip()

    # =====================================
    # (1) Similitud semántica sobre el JSON
    # =====================================
    if embeddings_base is not None and len(preguntas_base) > 0:
        embedding_usuario = modelo.encode(pregunta_original, convert_to_tensor=True)
        similitudes = util.cos_sim(embedding_usuario, embeddings_base)[0]
        idx = int(similitudes.argmax())
        score = float(similitudes[idx])

        pregunta_match = preguntas_base[idx]
        sql_match = base[idx].get("sql", "")

        # NO interpolar curso ni prefix aquí
        # - Dejamos {PREFIX} literal para que el backend lo reemplace.
        # - Dejamos __CURSO__ literal para que el backend lo parametrice.

        if score > 0.7 and es_solo_lectura(sql_match):
            return {
                "pregunta_match": pregunta_match,
                "sql": sql_match,
                "params": [],  # el backend calculará params según los __CURSO__ encontrados
                "score": round(score, 4),
                "explicacion": f"Coincidencia semántica del {round(score*100, 2)}% con: '{pregunta_match}'"
            }

    # ==========================================
    # (2) Fallback: IA con ejemplos del TXT (few-shots)
    # ==========================================
    sql_gpt = generar_sql_con_gpt(pregunta_original, curso)
    if es_solo_lectura(sql_gpt):
        return {
            "pregunta_match": "SQL generada por IA (con ejemplos del TXT)",
            "sql": sql_gpt,
            "params": [],  # el backend calculará params
            "score": 0.85,
            "explicacion": "No hubo coincidencia válida en JSON; se usó el TXT como guía para IA."
        }

    # =========================
    # (3) Sin resultados válidos
    # =========================
    return {
        "pregunta_match": None,
        "sql": "",
        "params": [],
        "score": 0.0,
        "explicacion": "No se pudo generar una consulta válida."
    }
