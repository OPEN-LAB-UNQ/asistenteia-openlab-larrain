¡Por supuesto! Aquí tienes el texto organizado con un formato Markdown limpio, utilizando jerarquías claras, listas y bloques de código para que sea mucho más fácil de leer y copiar.

ASISTENTE IA - OPEN LAB UNQ & HOSPITAL LARRAÍN
Este proyecto es una iniciativa conjunta de OPEN LAB - Universidad Nacional de Quilmes y el Hospital Mario Larraín de Berisso. Se trata de un asistente inteligente construido con Flask y Gunicorn, orientado a mejorar la gestión y el acceso a la información en entornos educativos y de salud, con un fuerte enfoque en ética, transparencia y privacidad.

ÍNDICE
ACCESO RÁPIDO

CARACTERÍSTICAS PRINCIPALES

TECNOLOGÍAS UTILIZADAS

REQUISITOS DEL SISTEMA

ESTRUCTURA DE ARCHIVOS

INSTALACIÓN PASO A PASO

EJECUCIÓN

MARCO ÉTICO

CONTACTO Y VERSIÓN

1. ACCESO RÁPIDO
SITIO WEB: https://asistenteia.entornodepruebas.com.ar/foro/

CLAVE ACCESO: 2817

2. CARACTERÍSTICAS PRINCIPALES
MARCO ÉTICO INTEGRADO: Alineado con la Guía Argentina de IA Responsable (2025) y recomendaciones de la UNESCO (Ver Sección 8 para detalle de principios).

SEGURIDAD ROBUSTA: Solo consultas SELECT en SQL y protección contra inyección SQL. Bloqueo estricto de prompt injection. Autenticación por clave de acceso y pool de conexiones a la base de datos.

FUNCIONALIDADES INTELIGENTES: Preguntas predefinidas por categoría y modo libre para consultas personalizadas. Sugerencias automáticas y análisis de sentimiento en foros. Detección de lenguaje ofensivo e identificación de preguntas sin respuesta.

ARQUITECTURA PROFESIONAL: Diseño modular con Blueprints y cache con TTL para consultas frecuentes. Preparado para alta concurrencia, con logs y trazabilidad de incidentes.

3. TECNOLOGÍAS UTILIZADAS
Lenguaje y Frameworks: Python 3.9+, Flask, Gunicorn.

Servidor y Seguridad: Nginx (Proxy reverso), Certbot / Let's Encrypt (SSL).

Base de Datos: MySQL.

Inteligencia Artificial: OpenAI API (Análisis de texto), Sentence Transformers (Búsqueda semántica).

Frontend: HTML / CSS / JavaScript.

4. REQUISITOS DEL SISTEMA
Servidor Linux (CentOS/RHEL/Fedora recomendado) con acceso root o sudo.

Puertos 3306 (MySQL) y 5000 (App) abiertos en el firewall.

Conexión a internet para la instalación de dependencias.

5. ESTRUCTURA DE ARCHIVOS
Plaintext
.env               # Variables de entorno (API keys, DB, clave)
app.py             # Aplicación principal Flask
foro.py            # Blueprint para sección foro
curso.py           # Blueprint para sección cursos
Extractor.py       # Módulo de extracción de datos
sql_base.json      # Preguntas frecuentes base
sql_ejemplos.json  # Ejemplos adicionales
foro_chat.js       # Lógica del frontend
state.js           # Estado del frontend
ui.js              # Interfaz de usuario
foro_chat.html     # Página principal del asistente
6. INSTALACIÓN PASO A PASO
PASO 1: Crear Directorio
(Subir todos los archivos por FTP a esta ubicación)

Bash
mkdir -p /home/asistenteia
cd /home/asistenteia
PASO 2: Configurar archivo .env
Crear el archivo .env en la raíz del proyecto con el siguiente contenido:

Fragmento de código
OPENAI_API_KEY=sk-proj-jki1UH7TLzQ8L4KGXCzMc23jFnQDKvroPRsWr-mN8yc8krsMr8yQV7z8VYcUNqXeLq9s5JRc7nT3BlbkFJACe3joOLR3zSaDJeQTmhTVz78WUJbG8ozcQlCsELHtfLSinXhINYK4rewYTTTTTTTTTTTTT
DB_HOST=vps-5380511-x.dattaweb.com
DB_USER=muqfnoyr_mood705
DB_PASSWORD='TTTTTTTTTTTTTTT'
DB_NAME=muqfnoyr_mood705
DB_PREFIX=mvlkl_
ACCESS_KEY=2817
PASO 3: Instalar Python y pip
Bash
yum install -y python3 python3-pip
pip3 install --upgrade pip
PASO 4: Instalar Dependencias
Bash
pip3 install Flask==3.1.1 gunicorn==23.0.0 mysql-connector-python==9.3.0 openai==1.97.0 sentence-transformers==3.4.0 torch==2.7.1 python-dotenv==1.1.1 rapidfuzz==3.13.0 cachetools==6.1.0 markdown2==2.5.4 numpy==2.0.2 transformers==4.53.2 scikit-learn==1.6.1 huggingface-hub==0.33.4 safetensors==0.5.3 tqdm==4.67.1 requests==2.31.0 urllib3==2.3.0
PASO 5: Configurar Puertos en Firewall
Asegurarse de habilitar los puertos indicados en los requisitos (ejemplo usando firewall-cmd):

Bash
firewall-cmd --zone=public --add-port=5000/tcp --permanent
firewall-cmd --zone=public --add-port=3306/tcp --permanent
firewall-cmd --reload
7. EJECUCIÓN
MODO DESARROLLO (Para pruebas):

Bash
cd /home/asistenteia
python app.py
La aplicación estará disponible en: http://tu-ip:5000/foro/

8. MARCO ÉTICO
El asistente sigue estrictamente el marco ético versión 2025-09-02, alineado con la Guía Argentina de IA Responsable (2025) y la Recomendación UNESCO sobre Ética de la IA (2021).

PRINCIPIOS FUNDAMENTALES:

Supervisión humana obligatoria.

Proporcionalidad e inocuidad.

Equidad y no discriminación.

Transparencia y explicabilidad.

Privacidad y protección de datos.

Seguridad, Inclusión y Accesibilidad.

Responsabilidad y auditoría.

PROHIBICIONES ESPECÍFICAS:

Exponer datos personales o sensibles.

Sugerir decisiones administrativas sin revisión humana.

Inventar datos o diagnósticos médicos (alucinaciones).

9. CONTACTO Y VERSIÓN
VERSIÓN: 1.0.1 - Marzo 2026

MARCO ÉTICO: 2025-09-02

LICENCIA: Distribuido bajo licencia MIT.

CONTACTO: Para soporte técnico o consultas éticas, contactar al responsable institucional: maximiliano.perez@unq.edu.ar
