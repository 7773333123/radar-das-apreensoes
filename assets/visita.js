/* Visitantes: avisa o servidor (api/visita.js), nunca no navegador do dono (marca de assets/dono.js).
   Só país, estado e cidade aproximados; nada aparece no site.
   - 1ª visita do dia do navegador = uma PESSOA;
   - volta depois de 10 min ou mais sem abrir o site = nova VISITA da mesma pessoa ("retorno", 24/11/2026).
   Uso por visita (dono do site, 26/11/2026: "quantos acessos cada um faz, quantas notícias, tempo e quando
   retornam"): um código ANÔNIMO sorteado e guardado só neste navegador (não é IP nem dado pessoal; some ao limpar
   os dados do navegador) junta as visitas da mesma pessoa. Conta só QUANTAS páginas e notícias foram abertas
   (não quais) e o tempo com o site na tela; o resumo vai num aviso ao sair da página (no máximo a cada 2 min). */
(function () {
  var ls;
  try { ls = window.localStorage; if (ls.getItem('radar_dono') === '1') return; } catch (e) { return; }
  var ler = function (k, d) { try { var v = JSON.parse(ls.getItem(k)); return v == null ? d : v; } catch (e) { return d; } };
  var gravar = function (k, v) { try { ls.setItem(k, JSON.stringify(v)); } catch (e) { /* sem registro */ } };
  var agora = Date.now();
  var hoje = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });

  // Código anônimo do navegador (sorteado; não identifica ninguém).
  var id = ler('radar_id', '');
  if (!/^[a-z0-9]{12}$/.test(id)) {
    var b = new Uint8Array(12);
    (window.crypto || {}).getRandomValues ? crypto.getRandomValues(b) : b.forEach(function (_, i) { b[i] = Math.random() * 256; });
    id = Array.prototype.map.call(b, function (x) { return 'abcdefghijklmnopqrstuvwxyz0123456789'[x % 36]; }).join('');
    gravar('radar_id', id);
  }

  // Visita: nova no primeiro acesso do dia ou depois de 10 min sem abrir o site.
  var ultima = Number(ls.getItem('radar_visita_ultima') || 0);
  var novoDia = ls.getItem('radar_visita_dia') !== hoje;
  var novaVisita = novoDia || agora - ultima >= 10 * 60 * 1000;
  ls.setItem('radar_visita_ultima', String(agora));
  var dias = ler('radar_dias', []);
  var sessao = ler('radar_sessao', null);
  if (novaVisita || !sessao) {
    var anterior = dias.filter(function (d) { return d !== hoje; }).slice(-1)[0] || '';
    if (dias[dias.length - 1] !== hoje) { dias.push(hoje); gravar('radar_dias', dias.slice(-90)); }
    var nDia = novoDia ? 1 : (ler('radar_visitas_hoje', 0) + 1);
    gravar('radar_visitas_hoje', nDia);
    sessao = { v: nDia, ini: agora, pags: 0, nots: 0, ms: 0, env: '' };
    ls.setItem('radar_visita_dia', hoje);
    var desde = anterior ? Math.round((Date.parse(hoje) - Date.parse(anterior)) / 864e5) : -1;
    var q = '?id=' + id + '&v=' + nDia + '&dias=' + dias.length + '&desde=' + desde + (novoDia ? '' : '&retorno=1');
    try { fetch('/api/visita' + q, { method: 'POST', keepalive: true }).catch(function () {}); } catch (e) { /* sem registro */ }
  }
  var salvar = function () { gravar('radar_sessao', sessao); };
  sessao.pags += 1;
  if (/^\/noticia\//.test(location.pathname) || /^#noticia-/.test(location.hash)) sessao.nots += 1;
  salvar();

  // Notícia aberta no leitor da página inicial (#noticia-ID) e filtros (#cat=..., #uf=...) = página vista.
  var hashAnterior = location.hash;
  window.addEventListener('hashchange', function () {
    if (location.hash === hashAnterior) return;
    hashAnterior = location.hash;
    if (/^#noticia-\d+$/.test(location.hash)) sessao.nots += 1; else if (location.hash) sessao.pags += 1;
    ls.setItem('radar_visita_ultima', String(Date.now()));
    salvar();
  });
  // O leitor abre a notícia com history.pushState (não dispara hashchange).
  var push = history.pushState;
  history.pushState = function (estado, t, url) {
    var r = push.apply(this, arguments);
    if (/#noticia-\d+$/.test(String(url || ''))) { hashAnterior = location.hash; sessao.nots += 1; salvar(); }
    return r;
  };

  // Tempo com o site na tela.
  var visivelDesde = document.visibilityState === 'visible' ? Date.now() : 0;
  var ultimoEnvio = 0;
  document.addEventListener('visibilitychange', function () {
    var t = Date.now();
    if (document.visibilityState === 'visible') { visivelDesde = t; ls.setItem('radar_visita_ultima', String(t)); return; }
    if (visivelDesde) { sessao.ms += t - visivelDesde; visivelDesde = 0; }
    salvar();
    var resumo = [sessao.pags, sessao.nots, Math.round(sessao.ms / 1000)].join(',');
    if (resumo === sessao.env || t - ultimoEnvio < 120000) return;
    ultimoEnvio = t;
    sessao.env = resumo;
    salvar();
    var dados = JSON.stringify({ id: id, v: sessao.v, pags: sessao.pags, nots: sessao.nots, seg: Math.round(sessao.ms / 1000),
      ini: new Date(sessao.ini).toISOString().slice(0, 16) + 'Z' });
    try {
      if (!navigator.sendBeacon || !navigator.sendBeacon('/api/visita?ev=uso', new Blob([dados], { type: 'text/plain' }))) {
        fetch('/api/visita?ev=uso', { method: 'POST', body: dados, keepalive: true }).catch(function () {});
      }
    } catch (e) { /* sem registro */ }
  });
})();
