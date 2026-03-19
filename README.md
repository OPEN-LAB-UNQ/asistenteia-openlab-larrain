# ASISTENTE IA - OPEN LAB UNQ & HOSPITAL LARRAÍN

Este proyecto es una iniciativa conjunta de OPEN LAB - Universidad Nacional de Quilmes y el Hospital Mario Larraín de Berisso.

Se trata de un asistente inteligente construido con Flask y Gunicorn, orientado a mejorar la gestión y el acceso a la información en entornos educativos y de salud, con un fuerte enfoque en ética, transparencia y privacidad.

---

## INDICE

1. Acceso Rápido  
2. Características Principales  
3. Tecnologías Utilizadas  
4. Requisitos del Sistema  
5. Estructura de Archivos  
6. Instalación Paso a Paso  
7. Ejecución  
8. Marco Ético  
9. Contacto y Versión  

---

## 1. ACCESO RAPIDO

Sitio Web:  
https://asistenteia.entornodepruebas.com.ar/foro/

Clave de acceso:  
2817

---

## 2. CARACTERISTICAS PRINCIPALES

### Marco Ético Integrado
- Alineado con la Guía Argentina de IA Responsable (2025)  
- Basado en recomendaciones de UNESCO  

### Seguridad Robusta
- Solo consultas SELECT en SQL  
- Protección contra inyección SQL  
- Bloqueo de prompt injection  
- Autenticación por clave  
- Pool de conexiones a la base de datos  

### Funcionalidades Inteligentes
- Preguntas predefinidas por categoría  
- Modo libre para consultas personalizadas  
- Sugerencias automáticas  
- Análisis de sentimiento en foros  
- Detección de lenguaje ofensivo  
- Identificación de preguntas sin respuesta  

### Arquitectura Profesional
- Diseño modular con Flask Blueprints  
- Cache con TTL para consultas frecuentes  
- Preparado para alta concurrencia  
- Logs y trazabilidad  

---

## 3. TECNOLOGIAS UTILIZADAS

- Python 3.9+, Flask, Gunicorn  
- Nginx, Certbot / Let's Encrypt  
- MySQL  
- OpenAI API  
- Sentence Transformers  
- HTML, CSS, JavaScript  

---

## 4. REQUISITOS DEL SISTEMA

- Servidor Linux (CentOS / RHEL / Fedora recomendado)  
- Acceso root o sudo  
- Puertos abiertos:
  - 3306 (MySQL)
  - 5000 (App)  
- Conexión a internet  

---

## 5. ESTRUCTURA DE ARCHIVOS

```
.env
app.py
foro.py
curso.py
Extractor.py
sql_base.json
sql_ejemplos.json
foro_chat.js
state.js
ui.js
foro_chat.html
```

---

## 6. INSTALACION PASO A PASO

### Paso 1: Crear Directorio

```bash
mkdir -p /home/asistenteia
cd /home/asistenteia
```

(Subir archivos por FTP)

---

### Paso 2: Configurar .env

```env
OPENAI_API_KEY=TU_API_KEY
DB_HOST=vps-5380511-x.dattaweb.com
DB_USER=muqfnoyr_mood705
DB_PASSWORD=TU_PASSWORD
DB_NAME=muqfnoyr_mood705
DB_PREFIX=mvlkl_
ACCESS_KEY=2817
```

---

### Paso 3: Instalar Python

```bash
yum install -y python3 python3-pip
pip3 install --upgrade pip
```

---

### Paso 4: Instalar Dependencias

```bash
pip3 install Flask==3.1.1 gunicorn==23.0.0 mysql-connector-python==9.3.0 openai==1.97.0 sentence-transformers==3.4.0 torch==2.7.1 python-dotenv==1.1.1 rapidfuzz==3.13.0 cachetools==6.1.0 markdown2==2.5.4 numpy==2.0.2 transformers==4.53.2 scikit-learn==1.6.1 huggingface-hub==0.33.4 safetensors==0.5.3 tqdm==4.67.1 requests==2.31.0 urllib3==2.3.0
```

---

### Paso 5: Configurar Firewall

```bash
firewall-cmd --zone=public --add-port=5000/tcp --permanent
firewall-cmd --zone=public --add-port=3306/tcp --permanent
firewall-cmd --reload
```

---

## 7. EJECUCION

```bash
cd /home/asistenteia
python app.py
```

Disponible en:  
http://tu-ip:5000/foro/

---

## 8. MARCO ETICO

Alineado con:
- Guía Argentina de IA Responsable (2025)  
- UNESCO (2021)

### Principios
- Supervisión humana  
- Equidad  
- Transparencia  
- Privacidad  
- Seguridad  
- Responsabilidad  

### Prohibiciones
- Exponer datos sensibles  
- Automatizar decisiones sin control humano  
- Inventar datos o diagnósticos  

---

## 9. CONTACTO Y VERSION

- Versión: 1.0.1 – Marzo 2026  
- Licencia: MIT  

Contacto:  
maximiliano.perez@unq.edu.ar
