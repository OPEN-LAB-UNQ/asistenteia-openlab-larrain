export let modoLibre = false;

export let state = {
  page: 1,
  size: 100,
  lastPayload: null,
  // 👇 Por defecto arranca en false si no hay nada en localStorage
  consentIA: (localStorage.getItem("consent_ia") === "1"),
  chatSugerencias: [] // ✅ guarda las últimas sugerencias del chat
};