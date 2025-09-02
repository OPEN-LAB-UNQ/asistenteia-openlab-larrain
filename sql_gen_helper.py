# sql_gen_helper.py
# ------------------------------------------------------------
# Generador de SQL a partir de frases (solo lectura) para Moodle
# - Patrones -> plantillas SQL con {PREFIX}, {CURSO_ID}, {QUIZ_ID}, {ASSIGN_ID}
# - Resolución difusa de entidades contra la BD (cursos, foros, quizzes, assigns)
# - Lectura de DB_PREFIX desde .env (solo para consultas internas; NO se reemplaza {PREFIX})
# - Devuelve: {"ok": bool, "sql": str|None, "explicacion": str, "meta": dict}
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import time
import unicodedata
import mysql.connector
from typing import Optional, List, Tuple, Dict, Any
from dotenv import load_dotenv
from rapidfuzz import process, fuzz

# ------------------------
# Config & helpers básicos
# ------------------------
def _load_env():
    candidatos = ["/home/asistenteia/.env", ".env"]
    for p in candidatos:
        if os.path.exists(p):
            load_dotenv(dotenv_path=p)
            return p
    load_dotenv()
    return None

_ENV_LOADED_FROM = _load_env()
DB_PREFIX = os.getenv("DB_PREFIX", "").strip()
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "port": int(os.getenv("DB_PORT", 3306) if os.getenv("DB_PORT") else 3306),
    "connection_timeout": 10,
}

if not DB_PREFIX:
    raise ValueError("DB_PREFIX no definido en .env (requerido por sql_gen_helper.py)")

LEER_RE = re.compile(r'^\s*(SELECT|WITH)\b', re.IGNORECASE)

def es_solo_lectura(sql: str) -> bool:
    partes = [p.strip() for p in (sql or "").split(";") if p.strip()]
    return bool(partes) and all(LEER_RE.match(s) for s in partes)

def _norm(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s

def _conn():
    return mysql.connector.connect(**DB_CONFIG)

# ------------------------
# Caché liviana (60 segundos)
# ------------------------
_CACHE: Dict[str, Dict[str, Any]] = {
    "cursos": {"ts": 0.0, "data": []},
    "foros": {},
    "quizzes": {},
    "assigns": {},
}
_TTL = 60.0

def _get_cache(bucket: str, key: Optional[str] = None):
    now = time.time()
    if key is None:
        entry = _CACHE.get(bucket, {})
        if entry and now - entry.get("ts", 0) <= _TTL:
            return entry.get("data", [])
        return None
    else:
        entry = _CACHE[bucket].get(key, {})
        if entry and now - entry.get("ts", 0) <= _TTL:
            return entry.get("data", [])
        return None

def _set_cache(bucket: str, data, key: Optional[str] = None):
    now = time.time()
    if key is None:
        _CACHE[bucket] = {"ts": now, "data": data}
    else:
        _CACHE[bucket][key] = {"ts": now, "data": data}

# --------------------------------
# Resolución de entidades (difusa)
# --------------------------------
def listar_cursos() -> List[Tuple[int, str]]:
    cached = _get_cache("cursos")
    if cached is not None:
        return cached
    try:
        sql = f"SELECT id, fullname FROM {DB_PREFIX}course ORDER BY fullname"
        with _conn() as cn:
            cur = cn.cursor()
            cur.execute(sql)
            data = [(r[0], r[1]) for r in cur.fetchall()]
        _set_cache("cursos", data)
        return data
    except Exception as e:
        print(f"⚠️ Error listar_cursos: {e}")
        return []

def listar_foros_por_curso(course_id: int) -> List[Tuple[int, str]]:
    key = str(course_id)
    cached = _get_cache("foros", key)
    if cached is not None:
        return cached
    try:
        sql = f"SELECT f.id, f.name FROM {DB_PREFIX}forum f WHERE f.course = %s ORDER BY f.name"
        with _conn() as cn:
            cur = cn.cursor()
            cur.execute(sql, (course_id,))
            data = [(r[0], r[1]) for r in cur.fetchall()]
        _set_cache("foros", data, key)
        return data
    except Exception as e:
        print(f"⚠️ Error listar_foros_por_curso({course_id}): {e}")
        return []

def listar_quizzes_por_curso(course_id: int) -> List[Tuple[int, str]]:
    key = str(course_id)
    cached = _get_cache("quizzes", key)
    if cached is not None:
        return cached
    try:
        sql = f"SELECT q.id, q.name FROM {DB_PREFIX}quiz q WHERE q.course = %s ORDER BY q.name"
        with _conn() as cn:
            cur = cn.cursor()
            cur.execute(sql, (course_id,))
            data = [(r[0], r[1]) for r in cur.fetchall()]
        _set_cache("quizzes", data, key)
        return data
    except Exception as e:
        print(f"⚠️ Error listar_quizzes_por_curso({course_id}): {e}")
        return []

def listar_assigns_por_curso(course_id: int) -> List[Tuple[int, str, int]]:
    """Devuelve (id, name, duedate) de las tareas del curso."""
    key = str(course_id)
    cached = _get_cache("assigns", key)
    if cached is not None:
        return cached
    try:
        sql = f"""
            SELECT a.id, a.name, a.duedate
            FROM {DB_PREFIX}assign a
            WHERE a.course = %s
            ORDER BY a.name
        """
        with _conn() as cn:
            cur = cn.cursor()
            cur.execute(sql, (course_id,))
            data = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        _set_cache("assigns", data, key)
        return data
    except Exception as e:
        print(f"⚠️ Error listar_assigns_por_curso({course_id}): {e}")
        return []

UMBRAL_COINCIDENCIA = 90  # más estricto para minimizar falsos positivos

def _resolver_best_match(nombre_usuario: str, candidatos: List[str], umbral: int = UMBRAL_COINCIDENCIA):
    if not candidatos:
        return None
    best = process.extractOne(
        _norm(nombre_usuario),
        [_norm(c) for c in candidatos],
        scorer=fuzz.token_sort_ratio
    )
    if not best:
        return None
    score = best[1]
    idx   = best[2]
    return (idx, score) if score >= umbral else None

def _resolver_curso_por_nombre(nombre_usuario: str) -> Optional[Dict[str, Any]]:
    cursos = listar_cursos()
    if not cursos:
        return None
    nombres = [c[1] for c in cursos]
    mm = _resolver_best_match(nombre_usuario, nombres, umbral=UMBRAL_COINCIDENCIA)
    if not mm:
        return None
    idx, score = mm
    return {"id": cursos[idx][0], "fullname": cursos[idx][1], "score": score}

def _resolver_quiz_en_curso(nombre_quiz: str, course_id: int) -> Optional[Dict[str, Any]]:
    quizzes = listar_quizzes_por_curso(course_id)
    if not quizzes:
        return None
    nombres = [q[1] for q in quizzes]
    mm = _resolver_best_match(nombre_quiz, nombres, umbral=UMBRAL_COINCIDENCIA)
    if not mm:
        return None
    idx, score = mm
    return {"id": quizzes[idx][0], "name": quizzes[idx][1], "score": score}

def _resolver_assign_en_curso(nombre_assign: str, course_id: int) -> Optional[Dict[str, Any]]:
    assigns = listar_assigns_por_curso(course_id)
    if not assigns:
        return None
    nombres = [a[1] for a in assigns]
    mm = _resolver_best_match(nombre_assign, nombres, umbral=UMBRAL_COINCIDENCIA)
    if not mm:
        return None
    idx, score = mm
    a = assigns[idx]
    return {"id": a[0], "name": a[1], "duedate": a[2], "score": score}

# ---------------------------------------
# Patrones -> Plantillas SQL (solo lectura)
# ---------------------------------------
PATRONES = [
    # Nivel plataforma
    {
        "id": "count_cursos_plataforma",
        "regex": re.compile(r"^(cuantos|cuántos|cantidad\s+de)\s+cursos(\s+(hay|existen))?", re.IGNORECASE),
        "sql": "SELECT COUNT(*) AS cantidad FROM {PREFIX}course;",
        "scope": "plataforma",
        "slots": []
    },
    {
        "id": "count_foros_plataforma",
        "regex": re.compile(r"^(cuantos|cuántos|cantidad\s+de)\s+foros(\s+(hay|existen))?", re.IGNORECASE),
        "sql": "SELECT COUNT(*) AS cantidad FROM {PREFIX}forum;",
        "scope": "plataforma",
        "slots": []
    },
    {
        "id": "count_usuarios_estudiantes_plataforma",
        "regex": re.compile(r"^(cuantos|cuántos|cantidad\s+de)\s+(alumnos|estudiantes)(\s+(hay|existen))?", re.IGNORECASE),
        "sql": (
            "SELECT COUNT(DISTINCT u.id) AS cantidad "
            "FROM {PREFIX}user u "
            "JOIN {PREFIX}role_assignments ra ON ra.userid = u.id "
            "WHERE ra.roleid = 5 AND u.deleted = 0;"
        ),
        "scope": "plataforma",
        "slots": []
    },

    # Nivel curso
    {
        "id": "count_estudiantes_curso",
        "regex": re.compile(r"^(cuantos|cuántos|cantidad\s+de)\s+(alumnos|estudiantes)\s+(hay|existen)\s+en\s+", re.IGNORECASE),
        "sql": (
            "SELECT COUNT(DISTINCT u.id) AS cantidad "
            "FROM {PREFIX}user u "
            "JOIN {PREFIX}user_enrolments ue ON ue.userid = u.id "
            "JOIN {PREFIX}enrol e ON e.id = ue.enrolid "
            "JOIN {PREFIX}course c ON c.id = e.courseid "
            "JOIN {PREFIX}context ctx ON ctx.instanceid = c.id AND ctx.contextlevel = 50 "
            "JOIN {PREFIX}role_assignments ra ON ra.userid = u.id AND ra.contextid = ctx.id "
            "WHERE c.id = {CURSO_ID} AND ra.roleid = 5;"
        ),
        "scope": "curso",
        "slots": ["CURSO"]
    },
    {
        "id": "count_foros_curso",
        "regex": re.compile(r"^(cuantos|cuántos|cantidad\s+de)\s+foros\s+(hay|existen)\s+en\s+", re.IGNORECASE),
        "sql": "SELECT COUNT(*) AS cantidad FROM {PREFIX}forum f WHERE f.course = {CURSO_ID};",
        "scope": "curso",
        "slots": ["CURSO"]
    },
    {
        "id": "promedio_curso",
        "regex": re.compile(r"^(cual|cuál)\s+es\s+el\s+promedio(\s+general)?\s+del\s+curso", re.IGNORECASE),
        "sql": (
            "SELECT ROUND(AVG(gg.finalgrade), 2) AS promedio "
            "FROM {PREFIX}grade_grades gg "
            "JOIN {PREFIX}grade_items gi ON gg.itemid = gi.id "
            "WHERE gi.courseid = {CURSO_ID};"
        ),
        "scope": "curso",
        "slots": ["CURSO"]
    },
    {
        "id": "intentos_quiz_en_curso",
        "regex": re.compile(r"^(cuantos|cuántos)\s+intentos\s+(tiene|se\s+h(i|a)n\s+hecho)\s+el\s+quiz\s+", re.IGNORECASE),
        "sql": (
            "SELECT COUNT(*) AS intentos "
            "FROM {PREFIX}quiz_attempts qa "
            "JOIN {PREFIX}quiz q ON qa.quiz = q.id "
            "WHERE q.id = {QUIZ_ID};"
        ),
        "scope": "curso",
        "slots": ["CURSO", "QUIZ"]
    },

    # Due date de actividad (assign)
    {
        "id": "duedate_assign_en_curso_es",
        "regex": re.compile(r"(fecha\s+de\s+finalizaci[oó]n|vencimiento|l[ií]mite|deadline|due\s+date).*(actividad|tarea|assign|entrega)", re.IGNORECASE),
        "sql": "SELECT a.name AS actividad, a.duedate FROM {PREFIX}assign a WHERE a.id = {ASSIGN_ID};",
        "scope": "curso",
        "slots": ["CURSO", "ASSIGN"]
    },
    {
        "id": "duedate_assign_en_curso_en",
        "regex": re.compile(r"(what\s+is\s+the\s+due\s+date|when\s+is\s+the\s+deadline).*(assignment|activity|deliverable|submission|task)", re.IGNORECASE),
        "sql": "SELECT a.name AS actividad, a.duedate FROM {PREFIX}assign a WHERE a.id = {ASSIGN_ID};",
        "scope": "curso",
        "slots": ["CURSO", "ASSIGN"]
    },
]

# -----------------------------------------------------
# Motor de interpretación -> Construcción final de SQL
# -----------------------------------------------------
def _buscar_patron(frase: str):
    f = _norm(frase)
    for p in PATRONES:
        if p["regex"].search(f):
            return p
    return None

def _extraer_nombre_despues_de(frase_norm: str, marcador: str) -> Optional[str]:
    idx = frase_norm.find(marcador)
    if idx == -1:
        return None
    nombre = frase_norm[idx + len(marcador):].strip()
    nombre = re.split(r'[?]|$|\.', nombre)[0].strip()
    return nombre if nombre else None

def build_sql_from_phrase(frase: str, curso_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Intenta generar SQL de solo lectura a partir de una frase.
    - NO reemplaza {PREFIX} (lo hará el backend).
    - Inserta IDs numéricos resueltos en {CURSO_ID}/{QUIZ_ID}/{ASSIGN_ID}.
    """
    if not frase or not frase.strip():
        return {"ok": False, "sql": None, "explicacion": "Frase vacía.", "meta": {}}

    patron = _buscar_patron(frase)
    if not patron:
        return {"ok": False, "sql": None, "explicacion": "Sin patrón coincidente.", "meta": {}}

    # Importante: dejamos {PREFIX} literal; NO lo reemplazamos por DB_PREFIX.
    sql_tpl = patron["sql"]
    meta = {"patron": patron["id"], "scope": patron["scope"]}

    f_norm = _norm(frase)

    # 1) CURSO
    curso_resuelto = None
    if "CURSO" in patron.get("slots", []):
        if curso_hint and curso_hint.strip() and _norm(curso_hint) != "__all__":
            curso_resuelto = _resolver_curso_por_nombre(curso_hint)
        if not curso_resuelto:
            nombre_curso = (
                _extraer_nombre_despues_de(f_norm, "en ") or
                _extraer_nombre_despues_de(f_norm, "del curso ") or
                _extraer_nombre_despues_de(f_norm, "en el curso ")
            )
            if nombre_curso:
                curso_resuelto = _resolver_curso_por_nombre(nombre_curso)

        if not curso_resuelto:
            return {"ok": False, "sql": None, "explicacion": "No pude identificar el curso.", "meta": meta}

        sql_tpl = sql_tpl.replace("{CURSO_ID}", str(curso_resuelto["id"]))
        meta["curso"] = curso_resuelto

    # 2) QUIZ
    if "QUIZ" in patron.get("slots", []):
        if not curso_resuelto:
            return {"ok": False, "sql": None, "explicacion": "Falta curso para ubicar el quiz.", "meta": meta}
        nombre_quiz = (
            _extraer_nombre_despues_de(f_norm, "el quiz ") or
            _extraer_nombre_despues_de(f_norm, "el cuestionario ") or
            _extraer_nombre_despues_de(f_norm, "el examen ")
        )
        if not nombre_quiz:
            return {"ok": False, "sql": None, "explicacion": "No pude identificar el nombre del quiz.", "meta": meta}

        quiz_res = _resolver_quiz_en_curso(nombre_quiz, curso_resuelto["id"])
        if not quiz_res:
            return {"ok": False, "sql": None, "explicacion": "No encontré un quiz que coincida.", "meta": meta}

        sql_tpl = sql_tpl.replace("{QUIZ_ID}", str(quiz_res["id"]))
        meta["quiz"] = quiz_res

    # 3) ASSIGN
    if "ASSIGN" in patron.get("slots", []):
        if not curso_resuelto:
            return {"ok": False, "sql": None, "explicacion": "Falta curso para ubicar la actividad.", "meta": meta}
        nombre_assign = (
            _extraer_nombre_despues_de(f_norm, "de la actividad ") or
            _extraer_nombre_despues_de(f_norm, "actividad ") or
            _extraer_nombre_despues_de(f_norm, "de la tarea ") or
            _extraer_nombre_despues_de(f_norm, "tarea ") or
            _extraer_nombre_despues_de(f_norm, "entrega ") or
            _extraer_nombre_despues_de(f_norm, "assign ") or
            _extraer_nombre_despues_de(f_norm, "assignment ")
        )
        if not nombre_assign:
            return {"ok": False, "sql": None, "explicacion": "No pude identificar el nombre de la actividad.", "meta": meta}

        assign_res = _resolver_assign_en_curso(nombre_assign, curso_resuelto["id"])
        if not assign_res:
            return {"ok": False, "sql": None, "explicacion": "No encontré una actividad que coincida.", "meta": meta}

        sql_tpl = sql_tpl.replace("{ASSIGN_ID}", str(assign_res["id"]))
        meta["assign"] = assign_res

    if not es_solo_lectura(sql_tpl):
        return {"ok": False, "sql": None, "explicacion": "La consulta no es de lectura.", "meta": meta}

    # Tip: si querés pedir confirmación en UI, podés usar meta['curso']['score']/<95 como gatillo
    return {"ok": True, "sql": sql_tpl, "explicacion": "Generada por patrones.", "meta": meta}
