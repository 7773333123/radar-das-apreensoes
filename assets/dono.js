/* Visitas do dono do site contadas à parte (Vercel Web Analytics).
   Abrir uma vez, em cada aparelho: https://www.radardasapreensoes.com.br/?sou-o-dono=1
   (para desfazer: ?sou-o-dono=0). Nesse navegador as páginas vistas não entram em Visitors e
   Page Views; cada página vira o evento "Visita do dono" (aba Events). Sem cookies; só uma marca
   guardada no próprio navegador. Carregado ANTES de /_vercel/insights/script.js. */
(function () {
  window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
  try {
    var p = new URLSearchParams(location.search);
    if (p.has('sou-o-dono')) {
      if (p.get('sou-o-dono') === '0') localStorage.removeItem('radar_dono');
      else localStorage.setItem('radar_dono', '1');
      p.delete('sou-o-dono');
      history.replaceState(history.state, '', location.pathname + (p.toString() ? '?' + p : '') + location.hash);
    }
    if (localStorage.getItem('radar_dono') !== '1') return;
    window.va('beforeSend', function (ev) {
      if (ev && ev.type === 'pageview') {
        var pagina = (ev.url ? new URL(ev.url).pathname : location.pathname).slice(0, 120);
        setTimeout(function () { window.va('event', { name: 'Visita do dono', data: { pagina: pagina } }); }, 0);
        return null;  // não conta como visitante nem página vista
      }
      return ev;
    });
  } catch (e) { /* sem marca: conta normalmente */ }
})();
