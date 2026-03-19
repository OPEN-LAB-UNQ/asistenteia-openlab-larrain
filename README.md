# ASISTENTE IA - OPEN LAB UNQ & HOSPITAL LARRAÍN

## Descripción

Este proyecto es una iniciativa conjunta de OPEN LAB - Universidad Nacional de Quilmes y el Hospital Mario Larraín de Berisso.

Se trata de un asistente inteligente construido con Flask y Gunicorn, orientado a mejorar la gestión y el acceso a la información en entornos educativos y de salud, con un fuerte enfoque en ética, transparencia y privacidad.

---

## Índice

1. Acceso rápido  
2. Características principales  
3. Arquitectura del sistema  
4. Tecnologías utilizadas  
5. Requisitos del sistema  
6. Estructura del proyecto  
7. Instalación  
8. Ejecución  
9. Uso de la API  
10. Motor de inteligencia artificial  
11. Seguridad  
12. Anonimización de datos  
13. Marco ético  
14. Licencia y contacto  

---

## 1. Acceso rápido

Sitio web:  
https://asistenteia.entornodepruebas.com.ar/foro/

Clave de acceso:  
2817

---

## 2. Características principales

- Consultas en lenguaje natural sobre datos académicos  
- Ejecución automática de consultas SQL seguras  
- Sugerencias inteligentes basadas en similitud semántica  
- Análisis de contenido de foros mediante IA  
- Detección de patrones (emocionales, participación, etc.)  
- Sistema modular escalable  

---

## 3. Arquitectura del sistema

El sistema está basado en una arquitectura web modular:

- Backend en Flask con Blueprints:
  - `/foro` → procesamiento de preguntas
  - `/curso` → listado de cursos
- Base de datos MySQL
- Motor de IA híbrido (reglas + embeddings + OpenAI)
- Frontend en HTML + JavaScript

### Flujo de procesamiento

1. El usuario realiza una pregunta
2. Se busca coincidencia en base predefinida
3. Se aplica búsqueda semántica si no hay match exacto
4. Se genera y valida la consulta SQL
5. Se ejecuta en la base de datos
6. Opcionalmente se analiza el resultado con IA
7. Se devuelve respuesta estructurada

---

## 4. Tecnologías utilizadas

- Python 3.9+
- Flask
- Gunicorn
- Nginx
- Certbot (SSL)
- MySQL
- OpenAI API
- Sentence Transformers
- HTML / CSS / JavaScript

---

## 5. Requisitos del sistema

- Servidor Linux
- Acceso root o sudo
- Puertos abiertos:
  - 3306 (MySQL)
  - 5000 (App)
- Conexión a internet

---

## 6. Estructura del proyecto

```
asistenteia/
├── static/
│   ├── app.js
│   ├── ui.js
│   ├── state.js
│   ├── foro_chat.css
├── templates/
│   └── foro_chat.html
├── app.py
├── foro.py
├── curso.py
├── extractor.py
├── sql_base.json
├── sql_ejemplos.json
├── MARCO_ETICO.txt
├── LICENSE
```

---

## 7. Instalación

### Crear directorio

```bash
mkdir -p /home/asistenteia
cd /home/asistenteia
```

### Configurar variables de entorno

```env
OPENAI_API_KEY=TU_API_KEY
DB_HOST=host
DB_USER=user
DB_PASSWORD=password
DB_NAME=database
DB_PREFIX=prefix_
ACCESS_KEY=2817
```

### Instalar dependencias

```bash
pip install Flask gunicorn mysql-connector-python openai sentence-transformers torch python-dotenv rapidfuzz cachetools
```

---

## 8. Ejecución

Modo desarrollo:

```bash
python app.py
```

Producción:

```bash
gunicorn -w 3 -b 127.0.0.1:8000 app:app
```

---

## 9. Uso de la API

Ejemplo de consulta:

```bash
curl -X POST http://localhost:8000/foro/procesar \
  -H "Content-Type: application/json" \
  -H "x-pass: 2817" \
  -d '{"pregunta": "¿Cuántos estudiantes hay?", "curso": "Matemática"}'
```

---

## 10. Motor de inteligencia artificial

El sistema combina múltiples estrategias:

- Búsqueda por similitud semántica (Sentence Transformers)
- Reranking con modelos de lenguaje
- Generación de análisis contextual con OpenAI

Permite:

- Interpretar preguntas abiertas
- Analizar mensajes de foros
- Detectar patrones y tendencias

---

## 11. Seguridad

- Solo se permiten consultas SQL de lectura (SELECT / WITH)
- Validación estricta contra inyección SQL
- Protección contra prompt injection
- Autenticación mediante clave de acceso
- Control de acceso a endpoints

---

## 12. Anonimización de datos

El sistema implementa anonimización previa al uso de inteligencia artificial.

Antes de enviar datos a modelos:

- Se reemplazan nombres por identificadores anónimos
- Se normalizan variantes lingüísticas
- Se preserva el contexto del diálogo

Además:

- No se envían datos sensibles
- Se minimiza la información procesada
- Se respeta la privacidad de los usuarios

Esto permite realizar análisis avanzados sin comprometer la identidad de las personas.

---

## 13. Marco ético

El sistema se alinea con:

- Guía Argentina de IA Responsable (2025)
- UNESCO (2021)

Principios:

- Supervisión humana
- Transparencia
- Equidad
- Privacidad
- Responsabilidad

Prohibiciones:

- Exponer datos personales
- Automatizar decisiones críticas
- Generar información falsa

---

## 14. Licencia y contacto

Licencia: MIT

Contacto:  
maximiliano.perez@unq.edu.ar
