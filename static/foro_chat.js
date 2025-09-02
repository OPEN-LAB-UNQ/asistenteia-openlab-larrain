// foro_chat.js (con botón "Volver a sugeridas" + paginación)
let modoLibre = false;

// Estado de paginación (persistente entre consultas)
let state = {
  page: 1,
  size: 100,   // si agregás <select id="page-size"> en el HTML, se toma de ahí
  lastPayload: null, // para re-disparar con otra página
};

document.addEventListener("DOMContentLoaded", () => {
  // si hay selector de tamaño de página en el DOM, úsalo
  const pageSizeSel = document.getElementById("page-size");
  if (pageSizeSel && pageSizeSel.value) {
    const n = parseInt(pageSizeSel.value, 10);
    if (!isNaN(n) && n > 0) state.size = n;
    pageSizeSel.addEventListener("change", () => {
      const v = parseInt(pageSizeSel.value, 10);
      if (!isNaN(v) && v > 0) {
        state.size = v;
        state.page = 1; // al cambiar tamaño, volvemos a página 1
        // si ya hay una consulta anterior, reintentar con nuevo size
        if (state.lastPayload) reenviarUltimaConsulta();
      }
    });
  }

  cargarCursos();
  document.getElementById("curso").addEventListener("change", () => {
    state.page = 1; // al cambiar curso, reiniciar página
    cargarPreguntasSegunCurso();
  });

  // Enter en el input libre envía
  const input = document.getElementById("pregunta");
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") enviarPregunta();
    if (e.key === "Escape" && modoLibre) setModoLibre(false); // ESC vuelve a sugeridas
  });

  // Deshabilitar Enviar si no hay texto (en libre) y no hay FAQ
  const faq = document.getElementById("faq");
  const btnEnviar = document.getElementById("btn-enviar");
  const updateEnviarState = () => {
    const manual = input.value.trim();
    btnEnviar.disabled = modoLibre ? manual.length === 0 : (faq.value.trim().length === 0 && manual.length === 0);
  };
  input.addEventListener("input", updateEnviarState);
  faq.addEventListener("change", updateEnviarState);
  updateEnviarState();

  // Botón Volver
  const btnVolver = document.getElementById("btn-volver");
  if (btnVolver) btnVolver.addEventListener("click", () => setModoLibre(false));
});

function setModoLibre(on) {
  modoLibre = !!on;
  const bloqueE = document.getElementById("bloque-estructuradas");
  const manual  = document.getElementById("manual-group");
  const wrapVolver = document.getElementById("wrap-volver");

  if (modoLibre) {
    bloqueE.classList.add("oculto");
    bloqueE.setAttribute("aria-hidden", "true");
    manual.classList.remove("oculto");
    manual.setAttribute("aria-hidden", "false");
    wrapVolver?.classList.remove("oculto");
    document.getElementById("pregunta").focus();
  } else {
    manual.classList.add("oculto");
    manual.setAttribute("aria-hidden", "true");
    bloqueE.classList.remove("oculto");
    bloqueE.setAttribute("aria-hidden", "false");
    wrapVolver?.classList.add("oculto");
    // limpiar input libre para evitar confusiones
    const input = document.getElementById("pregunta");
    if (input) input.value = "";
  }

  // actualizar estado del botón Enviar
  const evt = new Event("input");
  document.getElementById("pregunta").dispatchEvent(evt);
}

function mostrarManual() {
  setModoLibre(true);
}

function toggleFAQ() {
  const instrucciones = document.getElementById("instrucciones");
  const hidden = instrucciones.classList.toggle("oculto");
  instrucciones.setAttribute("aria-hidden", hidden ? "true" : "false");
}

function enviarPregunta() {
  const selCurso = (document.getElementById("curso").value || "").trim();
  // "" => plataforma; si NO es "__ALL__", se envía el nombre del curso
  const curso = (selCurso === "__ALL__" || /todos los cursos/i.test(selCurso)) ? "" : selCurso;

  const faq = document.getElementById("faq").value;
  const manual = document.getElementById("pregunta").value.trim();
  const guardar = document.getElementById("guardar").checked;

  // prioridad: manual > faq
  const texto = manual || faq;

  if (!texto) {
    alert("Por favor escribí o seleccioná una pregunta.");
    return;
  }

  // NUEVO: flag para que el backend sepa si es modo libre
  const libre = modoLibre || (manual.length > 0);

  // Desactivar botón enviar y mostrar loader
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

  // Asegurar page/size actuales (si existe control en DOM, ya actualizó state.size)
  const payload = { curso, pregunta: texto, guardar, mensajes: [], libre, page: state.page, size: state.size };
  state.lastPayload = payload; // para reintentos/paginación

  fetch("/foro/procesar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(res => res.json())
    .then(data => {
      renderRespuesta(data);
    })
    .catch(err => {
      console.error(err);
      respuestaEl.innerHTML = "<div class='alerta-vacia'>Ocurrió un error al procesar la consulta.</div>";
    })
    .finally(() => {
      enviarBtn.disabled = false;
      enviarBtn.textContent = originalTxt;
    });
}

function renderRespuesta(data) {
  const respuestaEl = document.getElementById("respuesta");

  if (data.status === "error") {
    respuestaEl.innerHTML = `<div class="alerta-vacia">${data.message}</div>`;
    return;
  }

  // Rama de análisis IA
  if (data.ia && data.respuesta) {
    const textoIA = Array.isArray(data.respuesta)
      ? data.respuesta.map(r => Object.values(r)[0]).join("<br/>")
      : data.respuesta;
    respuestaEl.innerHTML = `
      <div class="panel-ia">
        <h4>Análisis IA</h4>
        <div>${textoIA}</div>
      </div>`;
    return;
  }

  // Datos tabulares + paginación
  if (data.respuesta && data.respuesta.length > 0) {
    const tabla = generarTabla(data.respuesta);
    const pager = renderPager(data);
    const meta = renderMeta(data);
    respuestaEl.innerHTML = `${meta}${tabla}${pager}`;
  } else {
    respuestaEl.innerHTML = `<div class="alerta-vacia">⚠️ No se encontraron datos para esta consulta.</div>`;
  }
}

function renderMeta(data) {
  // Muestra info básica de consulta: páginas/filas
  const page = data.page ?? state.page;
  const size = data.size ?? state.size;
  const count = data.count ?? (data.respuesta ? data.respuesta.length : 0);
  const ruta = data.ruta ? ` · fuente: <code>${escapeHtml(data.ruta)}</code>` : "";
  return `
    <div class="meta-consulta">
      <small>Página ${page} — ${count} filas (tamaño: ${size})${ruta}</small>
    </div>
  `;
}

function renderPager(data) {
  const page = data.page ?? state.page;
  const size = data.size ?? state.size;
  const hasMore = !!data.has_more;

  const prevDisabled = (page <= 1) ? "disabled" : "";
  const nextDisabled = (!hasMore) ? "disabled" : "";

  return `
    <div class="pager">
      <button ${prevDisabled} onclick="cambiarPagina(${page - 1})">◀ Anterior</button>
      <span>Página ${page}</span>
      <button ${nextDisabled} onclick="cambiarPagina(${page + 1})">Siguiente ▶</button>
    </div>
  `;
}

function cambiarPagina(nuevaPagina) {
  if (nuevaPagina < 1) return;
  state.page = nuevaPagina;
  reenviarUltimaConsulta();
}

function reenviarUltimaConsulta() {
  if (!state.lastPayload) return;
  const payload = { ...state.lastPayload, page: state.page, size: state.size };

  const respuestaEl = document.getElementById("respuesta");
  respuestaEl.innerHTML = `
    <div class="loader-wrapper">
      <div class="loader"></div>
      <div class="pensando">Cargando página ${state.page}…</div>
    </div>`;

  fetch("/foro/procesar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(r => r.json())
    .then(data => renderRespuesta(data))
    .catch(err => {
      console.error(err);
      respuestaEl.innerHTML = "<div class='alerta-vacia'>Ocurrió un error al paginar.</div>";
    });
}

function limpiar() {
  // limpiar campos
  document.getElementById("faq").value = "";
  document.getElementById("pregunta").value = "";
  document.getElementById("respuesta").innerHTML = "";

  // reset paginación
  state.page = 1;
  // mantener size (o leer de #page-size si existe)
  const pageSizeSel = document.getElementById("page-size");
  if (pageSizeSel && pageSizeSel.value) {
    const n = parseInt(pageSizeSel.value, 10);
    if (!isNaN(n) && n > 0) state.size = n;
  }

  state.lastPayload = null;
  // volver a modo estructurado
  setModoLibre(false);
}

function cargarCursos() {
  fetch("/curso/listar")
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

      state.page = 1; // al cargar, comenzamos en página 1
      cargarPreguntasSegunCurso(); // Inicializa preguntas al cargar cursos
    })
    .catch(err => {
      console.error("Error al cargar cursos:", err);
    });
}

function cargarPreguntasSegunCurso() {
  fetch("/foro/faq")
    .then(res => res.json())
    .then(data => {
      const curso = document.getElementById("curso").value;
      const select = document.getElementById("faq");
      select.innerHTML = "";

      const preguntas = (curso === "__ALL__") ? data.generales : data.por_curso;

      // placeholder
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
    .catch(err => {
      console.error("Error al cargar preguntas frecuentes:", err);
    });
}

function generarTabla(respuesta) {
  if (!respuesta || respuesta.length === 0) return "";

  const columnas = Object.keys(respuesta[0]);
  let html = "<table><thead><tr>";

  columnas.forEach(col => { html += `<th>${escapeHtml(col)}</th>`; });

  html += "</tr></thead><tbody>";

  respuesta.forEach(fila => {
    html += "<tr>";
    columnas.forEach(col => {
      const val = fila[col] ?? "";
      html += `<td>${escapeHtml(String(val))}</td>`;
    });
    html += "</tr>";
  });

  html += "</tbody></table>";
  return html;
}

// Pequeño helper para evitar XSS en celdas/labels
function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
