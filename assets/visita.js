/* Primeira visita: avisa o servidor (api/visita.js) uma vez por navegador; o servidor só registra
   se ainda não houver registro. Nunca no navegador do dono (marca de assets/dono.js). */
(function () {
  try {
    if (localStorage.getItem('radar_dono') === '1' || localStorage.getItem('radar_visita_enviada')) return;
    localStorage.setItem('radar_visita_enviada', '1');
    fetch('/api/visita', { method: 'POST', keepalive: true }).catch(function () {});
  } catch (e) { /* sem registro */ }
})();
