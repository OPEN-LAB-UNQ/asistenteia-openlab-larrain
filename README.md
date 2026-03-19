# ASISTENTE IA - OPEN LAB UNQ & HOSPITAL LARRAÍN

Este proyecto es una iniciativa conjunta de OPEN LAB - Universidad Nacional de Quilmes y el Hospital Mario Larraín de Berisso. Se trata de un asistente inteligente construido con Flask y Gunicorn, orientado a mejorar la gestión y el acceso a la información en entornos educativos y de salud, con un fuerte enfoque en ética, transparencia y privacidad.

---

## ÍNDICE

1. ACCESO RÁPIDO  
2. CARACTERÍSTICAS PRINCIPALES  
3. TECNOLOGÍAS UTILIZADAS  
4. REQUISITOS DEL SISTEMA  
5. ESTRUCTURA DE ARCHIVOS  
6. INSTALACIÓN PASO A PASO  
7. EJECUCIÓN  
8. MARCO ÉTICO  
9. ANONIMIZACIÓN Y PRIVACIDAD  
10. CONTACTO Y VERSIÓN  

---

## 1. ACCESO RÁPIDO

SITIO WEB:  
https://asistenteia.entornodepruebas.com.ar/foro/

CLAVE ACCESO:  
2817

---

## 2. CARACTERÍSTICAS PRINCIPALES

### MARCO ÉTICO INTEGRADO
- Alineado con la Guía Argentina de IA Responsable (2025) y recomendaciones de la UNESCO  
- Integración directa del marco ético en el procesamiento del sistema  

### SEGURIDAD ROBUSTA
- Solo consultas SELECT en SQL y protección contra inyección SQL  
- Bloqueo estricto de prompt injection  
- Autenticación por clave de acceso  
- Pool de conexiones a la base de datos  
- Validación de consultas antes de ejecución  

### FUNCIONALIDADES INTELIGENTES
- Preguntas predefinidas por categoría  
- Modo libre para consultas personalizadas  
- Sugerencias automáticas mediante similitud semántica  
- Análisis de sentimiento en foros  
- Detección de lenguaje ofensivo  
- Identificación de preguntas sin respuesta  
- Análisis contextual de conversaciones con IA  

### ARQUITECTURA PROFESIONAL
- Diseño modular con Blueprints (Flask)  
- Cache con TTL para consultas frecuentes  
- Integración con modelos de embeddings (Sentence Transformers)  
- Reranking con modelos de lenguaje  
- Logs y trazabilidad de operaciones  
- Preparado para alta concurrencia  

---

## 3. TECNOLOGÍAS UTILIZADAS

- Lenguaje y Frameworks: Python 3.9+, Flask, Gunicorn  
- Servidor y Seguridad: Nginx (Proxy reverso), Certbot / Let's Encrypt (SSL)  
- Base de Datos: MySQL  
- Inteligencia Artificial: OpenAI API, Sentence Transformers  
- Frontend: HTML / CSS / JavaScript  

---

## 4. REQUISITOS DEL SISTEMA

- Servidor Linux (CentOS/RHEL/Fedora recomendado) con acceso root o sudo  
- Puertos 3306 (MySQL) y 5000 (App) abiertos en el firewall  
- Conexión a internet para la instalación de dependencias  

---

## 5. ESTRUCTURA DE ARCHIVOS

```
.env               # Variables de entorno (API keys, DB, clave)
app.py             # Aplicación principal Flask
foro.py            # Blueprint para sección foro
curso.py           # Blueprint para sección cursos
extractor.py       # Módulo de extracción de datos
sql_base.json      # Preguntas frecuentes base
sql_ejemplos.json  # Ejemplos adicionales

/static/
  app.js
  state.js
  ui.js
  foro_chat.css

/templates/
  foro_chat.html

MARCO_ETICO.txt
LICENSE
```

---

## 6. INSTALACIÓN PASO A PASO

### PASO 1: Crear Directorio

```bash
mkdir -p /home/asistenteia
cd /home/asistenteia
```

(Subir todos los archivos por FTP a esta ubicación)

---

### PASO 2: Configurar archivo .env

```env
OPENAI_API_KEY=TU_API_KEY
DB_HOST=host
DB_USER=user
DB_PASSWORD=password
DB_NAME=database
DB_PREFIX=prefix_
ACCESS_KEY=2817
```

---

### PASO 3: Instalar Python y pip

```bash
yum install -y python3 python3-pip
pip3 install --upgrade pip
```

---

### PASO 4: Instalar Dependencias

```bash
pip3 install Flask==3.1.1 gunicorn==23.0.0 mysql-connector-python==9.3.0 openai==1.97.0 sentence-transformers==3.4.0 torch==2.7.1 python-dotenv==1.1.1 rapidfuzz==3.13.0 cachetools==6.1.0 markdown2==2.5.4 numpy==2.0.2 transformers==4.53.2 scikit-learn==1.6.1 huggingface-hub==0.33.4 safetensors==0.5.3 tqdm==4.67.1 requests==2.31.0 urllib3==2.3.0
```

---

### PASO 5: Configurar Firewall

```bash
firewall-cmd --zone=public --add-port=5000/tcp --permanent
firewall-cmd --zone=public --add-port=3306/tcp --permanent
firewall-cmd --reload
```

---

## 7. EJECUCIÓN

Modo desarrollo:

```bash
cd /home/asistenteia
python app.py
```

Disponible en:  
http://tu-ip:5000/foro/

---

## 8. MARCO ÉTICO

El asistente sigue estrictamente el marco ético versión 2025-09-02, alineado con:

- Guía Argentina de IA Responsable (2025)  
- Recomendación UNESCO sobre Ética de la IA (2021)  

### PRINCIPIOS FUNDAMENTALES

- Supervisión humana obligatoria  
- Proporcionalidad e inocuidad  
- Equidad y no discriminación  
- Transparencia y explicabilidad  
- Privacidad y protección de datos  
- Seguridad, inclusión y accesibilidad  
- Responsabilidad y auditoría  

### PROHIBICIONES ESPECÍFICAS

- Exponer datos personales o sensibles  
- Sugerir decisiones administrativas sin revisión humana  
- Inventar datos o diagnósticos médicos  

---

## 9. ANONIMIZACIÓN Y PRIVACIDAD

El sistema implementa un mecanismo avanzado de anonimización antes de procesar datos con inteligencia artificial.

Antes de enviar información a modelos de lenguaje:

- Se reemplazan nombres reales por identificadores pseudónimos  
- Se normalizan variantes lingüísticas (acentos, diminutivos, etc.)  
- Se preserva la estructura conversacional  
- Se mantiene el contexto sin exponer identidades  

Además:

- No se envían datos sensibles ni credenciales  
- Se aplica el principio de minimización de datos  
- Se respeta la privacidad de los usuarios  

Este enfoque permite aprovechar capacidades de IA sin comprometer la confidencialidad de las personas.

---

## 10. CONTACTO Y VERSIÓN

VERSIÓN: 1.0.1 - Marzo 2026  
MARCO ÉTICO: 2025-09-02  
LICENCIA: MIT  

CONTACTO:  
maximiliano.perez@unq.edu.ar
