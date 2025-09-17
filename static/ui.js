import { state } from "./state.js";

export function initEticaUI() {
  const banner = document.getElementById("etica-banner");
  const chk = document.getElementById("consent-ia");
  const cerrar = document.getElementById("cerrar-banner");

  if (chk) {
    chk.checked = !!state.consentIA;
    chk.addEventListener("change", () => {
      state.consentIA = !!chk.checked;
      localStorage.setItem("consent_ia", state.consentIA ? "1" : "0");
    });
  }
  if (banner && localStorage.getItem("consent_ia") === null) {
    banner.classList.remove("oculto");
  }
  if (cerrar && banner) {
    cerrar.addEventListener("click", () => banner.classList.add("oculto"));
  }
}

export function setModoLibre(on) {
  const bloqueE = document.getElementById("bloque-estructuradas");
  const manual = document.getElementById("manual-group");

  const botonesNormales = document.getElementById("botones-normales");
  const botonesLibres = document.getElementById("botones-libres");
  const btnOtra = document.getElementById("btn-otra");

  if (on) {
    // Ocultar preguntas sugeridas, mostrar input manual
    bloqueE.classList.add("oculto");
    manual.classList.remove("oculto");

    // Cambiar botones
    botonesNormales.classList.add("oculto");
    botonesLibres.classList.remove("oculto");

    // Ocultar el botón "Hacer otra pregunta"
    if (btnOtra) btnOtra.classList.add("oculto");

    document.getElementById("pregunta").focus();
  } else {
    // Volver al modo sugeridas
    manual.classList.add("oculto");
    bloqueE.classList.remove("oculto");

    botonesNormales.classList.remove("oculto");
    botonesLibres.classList.add("oculto");

    // Mostrar de nuevo el botón "Hacer otra pregunta"
    if (btnOtra) btnOtra.classList.remove("oculto");

    document.getElementById("pregunta").value = "";
  }
}

/**
 * Renderiza la respuesta devuelta por el backend (procesar/chat)
 */
export function renderRespuesta(data) {
  const respuestaEl = document.getElementById("respuesta");

  // Mostrar SQL generada en un desplegable
  const queryBox = document.getElementById("query-sql");
  if (data.query) {
    queryBox.innerHTML = `
      <details>
        <summary>📜 Ver consulta SQL generada</summary>
        <pre>${escapeHtml(data.query)}</pre>
      </details>
    `;
    queryBox.classList.remove("oculto");
    queryBox.removeAttribute("aria-hidden");
  } else {
    queryBox.innerHTML = "";
    queryBox.classList.add("oculto");
    queryBox.setAttribute("aria-hidden", "true");
  }

  // ✅ Caso especial: respuesta IA en Markdown
  if (data.ia && data.respuesta && data.respuesta.length > 0 && data.respuesta[0]["Análisis IA"]) {
    const md = data.respuesta[0]["Análisis IA"];
    const htmlIA = window.marked.parse(md); // convertir Markdown a HTML
    const meta = renderMeta(data);
    respuestaEl.innerHTML = `
      ${meta}
      <div class="bloque-ia">
        <h3>🤖 Análisis IA</h3>
        <div class="ia-markdown">${htmlIA}</div>
      </div>
      ${buildEticaFooter(data)}
    `;
    return;
  }

  // ✅ Caso normal: tabla
  if (data.respuesta && data.respuesta.length > 0) {
    const tabla = generarTabla(data.respuesta);
    const meta = renderMeta(data);
    respuestaEl.innerHTML = `${meta}${tabla}${buildEticaFooter(data)}`;
  } else {
    respuestaEl.innerHTML = `<div class="alerta-vacia">⚠️ No se encontraron datos para esta consulta.</div>${buildEticaFooter(data)}`;
  }
}

export function generarTabla(respuesta) {
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

export function buildEticaFooter(data) {
  const ver = data.etica_version ? ` · marco ético: <code>${escapeHtml(data.etica_version)}</code>` : "";
  return `
    <div class="etica-foot">
      <small>⚖️ Sugerencia generada con criterios de ética y seguridad${ver}. Requiere revisión humana.</small>
    </div>`;
}

export function renderMeta(data) {
  const page = data.page ?? state.page;
  const size = data.size ?? state.size;
  const count = data.count ?? (data.respuesta ? data.respuesta.length : 0);
  const ruta = data.ruta ? ` · fuente: <code>${escapeHtml(data.ruta)}</code>` : "";
  return `
    <div class="meta-consulta">
      <small>Página ${page} — ${count} filas (tamaño: ${size})${ruta}</small>
    </div>`;
}

export function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
