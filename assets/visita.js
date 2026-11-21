/* Visitantes: avisa o servidor (api/visita.js) uma vez por dia por navegador, nunca no navegador do
   dono (marca de assets/dono.js). Só país, estado e cidade aproximados; nada aparece no site. */
(function () {
  try {
    if (localStorage.getItem('radar_dono') === '1') return;
    var hoje = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
    if (localStorage.getItem('radar_visita_dia') === hoje) return;
    localStorage.setItem('radar_visita_dia', hoje);
    fetch('/api/visita', { method: 'POST', keepalive: true }).catch(function () {});
  } catch (e) { /* sem registro */ }
})();
