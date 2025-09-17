import { state } from "./state.js";
import { initEticaUI, setModoLibre, renderRespuesta } from "./ui.js";

// =========================
// Gestión de clave de acceso
// =========================
function getClave() {
  let clave = localStorage.getItem("x-pass");
  if (!clave) {
    clave = prompt("🔑 Ingresá la clave de acceso:");
    if (clave) {
      localStorage.setItem("x-pass", clave);
    }
  }
  return clave || "";
}

// =========================
// Cursos y Preguntas Sugeridas
// =========================
function cargarCursos() {
  fetch("/curso/listar", {
    headers: { "x-pass": getClave() }
  })
    .then(res => res.json())
    .then(cursos => {
      const select = document.getElementById("curso");
      select.innerHTML = "";

      const opt = document.createElement("option");
      opt.value = "__ALL__";
      opt.textContent = "Todos los cursos";
      select.appendChild(opt);

      cursos.forEach(curso => {
        const option = document.createElement("option");
        option.value = curso;
        option.textContent = curso;
        select.appendChild(option);
      });

      state.page = 1;
      cargarPreguntasSegunCurso();
    })
    .catch(err => console.error("❌ Error al cargar cursos:", err));
}

function cargarPreguntasSegunCurso() {
  fetch("/foro/faq", {
    headers: { "x-pass": getClave() }
  })
    .then(res => res.json())
    .then(data => {
      const curso = document.getElementById("curso").value;
      const select = document.getElementById("faq");
      select.innerHTML = "";

      // ✅ Incluir tanto las preguntas normales como las IA
      const preguntas =
        curso === "__ALL__"
          ? [...(data.generales || []), ...(data.generales_ia || [])]
          : [...(data.por_curso || []), ...(data.por_curso_ia || [])];

      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent = "-- Elegí una pregunta --";
      select.appendChild(ph);

      preguntas.forEach(p => {
        const option = document.createElement("option");
        option.value = p;
        option.textContent = p;
        select.appendChild(option);
      });
    })
    .catch(err => console.error("❌ Error al cargar preguntas frecuentes:", err));
}

// =========================
// Enviar y Limpiar
// =========================
function enviarPregunta() {
  const selCurso = (document.getElementById("curso").value || "").trim();
  const curso =
    selCurso === "__ALL__" || /todos los cursos/i.test(selCurso) ? "" : selCurso;

  const faq = document.getElementById("faq").value;
  const manual = document.getElementById("pregunta").value.trim();
  const guardar = document.getElementById("guardar").checked;

  const texto = manual || faq;
  if (!texto) {
    alert("Por favor escribí o seleccioná una pregunta.");
    return;
  }

  const libre = state.modoLibre || manual.length > 0;
  const enviarBtn = document.getElementById("btn-enviar");
  enviarBtn.disabled = true;
  const originalTxt = enviarBtn.textContent;
  enviarBtn.textContent = "⏳ Procesando...";

  const respuestaEl = document.getElementById("respuesta");
  respuestaEl.innerHTML = `
    <div class="loader-wrapper">
      <div class="loader"></div>
      <div class="pensando">Generando respuesta…</div>
    </div>`;
  respuestaEl.scrollIntoView({ behavior: "smooth" });

  const payload = {
    curso,
    pregunta: texto,
    guardar,
    mensajes: [],
    libre,
    page: state.page,
    size: state.size,
    consentIA: state.consentIA
  };
  state.lastPayload = payload;

  fetch("/foro/procesar", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-pass": getClave()
    },
    body: JSON.stringify(payload)
  })
    .then(res => res.json())
    .then(data => {
      if (data.status === "sugerencias") {
        let html = `<div class="alerta-vacia">🤖 No encontré coincidencia exacta. Estas son las preguntas más cercanas:</div><ul>`;
        data.sugerencias.forEach((sug, i) => {
          html += `<li>
            <button class="sug-btn" onclick="ejecutarSugerencia(${i})">
              ${i + 1}) ${sug.pregunta}
            </button>
            ${
              sug.explicacion
                ? `<div class="mini-exp">💡 ${sug.explicacion}</div>`
                : ""
            }
            ${
              sug.descripcion
                ? `<div class="mini-desc">⚖️ ${sug.descripcion}</div>`
                : ""
            }
          </li>`;
        });
        html += "</ul>";
        respuestaEl.innerHTML = html;
        state.chatSugerencias = data.sugerencias;
      } else if (data.status === "ok") {
        renderRespuesta(data);
      } else {
        respuestaEl.innerHTML = `<div class='alerta-vacia'>⚠️ ${
          data.message || "Error inesperado"
        }</div>`;
      }
    })
    .catch(err => {
      console.error("❌ Error en enviarPregunta:", err);
      respuestaEl.innerHTML =
        "<div class='alerta-vacia'>Ocurrió un error al procesar la consulta.</div>";
    })
    .finally(() => {
      enviarBtn.disabled = false;
      enviarBtn.textContent = originalTxt;
    });
}

// Ejecutar una de las sugerencias
window.ejecutarSugerencia = function (idx) {
  if (
    !state.chatSugerencias ||
    idx < 0 ||
    idx >= state.chatSugerencias.length
  )
    return;

  const sugerencia = state.chatSugerencias[idx];
  const curso = (document.getElementById("curso").value || "").trim();
  const payload = {
    curso,
    seleccion: idx + 1,
    sugerencias: state.chatSugerencias,
    page: state.page,
    size: state.size
  };

  const resp = document.getElementById("respuesta");
  resp.innerHTML = `<div class="loader-wrapper"><div class="loader"></div><div class="pensando">Ejecutando la sugerencia…</div></div>`;

  fetch("/foro/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-pass": getClave()
    },
    body: JSON.stringify(payload)
  })
    .then(r => r.json())
    .then(data => renderRespuesta(data))
    .catch(err => {
      console.error("❌ Error al ejecutar sugerencia:", err);
      resp.innerHTML =
        "<div class='alerta-vacia'>⚠️ Hubo un error al ejecutar la sugerencia.</div>";
    });
};

function limpiar() {
  document.getElementById("faq").value = "";
  document.getElementById("pregunta").value = "";
  document.getElementById("respuesta").innerHTML = "";
  const chk = document.getElementById("guardar");
  if (chk) chk.checked = false;

  state.page = 1;
  state.size = 100;
  state.lastPayload = null;
  state.chatSugerencias = [];
  state.modoLibre = false;

  setModoLibre(false);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// =========================
// Init
// =========================
document.addEventListener("DOMContentLoaded", () => {
  initEticaUI();
  cargarCursos();
  document.getElementById("curso").addEventListener("change", () => {
    state.page = 1;
    cargarPreguntasSegunCurso();
  });
});

// =========================
// Exponer funciones
// =========================
window.enviarPregunta = enviarPregunta;
window.limpiar = limpiar;
window.setModoLibre = setModoLibre;
