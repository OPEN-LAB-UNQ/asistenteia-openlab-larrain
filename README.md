# asistenteia-openlab-larrain
Asistente inteligente institucional (Flask + Gunicorn + Nginx) desarrollado por OPEN LAB - UNQ y el Hospital Mario Larraín de Berisso.

Este proyecto es una iniciativa conjunta de **OPEN LAB - Universidad Nacional de Quilmes** y el **Hospital Mario Larraín de Berisso**.  
Se trata de un asistente inteligente construido con Flask y Gunicorn, orientado a mejorar la gestión y el acceso a la información en contextos institucionales.

---

## 🚀 Tecnologías

- Python
- Flask
- Gunicorn
- Nginx
- Certbot (Let's Encrypt)

---

## ⚙️ Instalación

Clonar el repositorio:

```bash
git clone https://github.com/tu-org/asistente-ia.git
cd asistente-ia

Instalar dependencias:
pip install -r requirements.txt

Ejecutar en modo desarrollo:
python app.py

Correr en producción con Gunicorn:
gunicorn -w 3 -b 127.0.0.1:8000 app:app


🌐 Despliegue recomendado
Gunicorn como servidor WSGI.
Nginx como proxy reverso.
Certbot para certificados SSL de Let's Encrypt.

📌 Ejemplo de uso
Consulta al endpoint del foro:
curl -X POST http://localhost:8000/foro/procesar \
  -H "Content-Type: application/json" \
  -d '{"pregunta": "¿Cuántos estudiantes hay en el curso de Matemática?", "curso": "Matemática"}'


📜 Licencia
Distribuido bajo la licencia MIT.
Ver LICENSE para más detalles.


👥 Créditos
OPEN LAB - Universidad Nacional de Quilmes
Hospital Mario Larraín de Berisso


