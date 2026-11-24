/* Visitantes: avisa o servidor (api/visita.js), nunca no navegador do dono (marca de assets/dono.js).
   Só país, estado e cidade aproximados; nada aparece no site.
   - 1ª visita do dia do navegador = uma PESSOA;
   - volta depois de 30 min ou mais sem abrir o site = nova VISITA da mesma pessoa ("retorno", 24/11/2026). */
(function () {
  try {
    if (localStorage.getItem('radar_dono') === '1') return;
    var agora = Date.now();
    var hoje = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
    var ultima = Number(localStorage.getItem('radar_visita_ultima') || 0);
    localStorage.setItem('radar_visita_ultima', String(agora));
    var novoDia = localStorage.getItem('radar_visita_dia') !== hoje;
    if (!novoDia && agora - ultima < 30 * 60 * 1000) return;  // mesma visita
    localStorage.setItem('radar_visita_dia', hoje);
    fetch('/api/visita' + (novoDia ? '' : '?retorno=1'), { method: 'POST', keepalive: true }).catch(function () {});
  } catch (e) { /* sem registro */ }
})();
