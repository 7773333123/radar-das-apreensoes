// Teste (manual, no GitHub): leitura na hora (api/_extrair.js) em notícias sem foto ou sem trecho.
const fs = require('fs');
const { lerNoticia } = require('../api/_extrair.js');
const feed = JSON.parse(fs.readFileSync('feed.json', 'utf8')).noticias;
const links = JSON.parse(fs.readFileSync('feed_links.json', 'utf8'));
const N = Number(process.argv[2] || 20);
const comLink = feed.filter((n) => n.u && !n.img).slice(0, N);
const google = feed.filter((n) => !n.u).slice(0, Math.ceil(N / 2));
(async () => {
  let ok = 0, fotos = 0, textos = 0;
  for (const n of [...comLink, ...google]) {
    const t0 = Date.now();
    let r = null, erro = '';
    try { r = await lerNoticia(n, links[n.i]); } catch (e) { erro = String(e.message || e).slice(0, 60); }
    const g = r?.g?.length || 0, tr = r?.tr?.length || 0, p = r?.p?.length || 0;
    if (r) ok++; if (g) fotos++; if (tr || p) textos++;
    console.log(`${n.u ? 'link  ' : 'google'} ${String(Date.now() - t0).padStart(5)}ms fotos=${g} trecho=${tr}${r?.tt ? ` (${Math.round(100 * tr / r.tt)}%)` : ''} oficial=${p} ${erro} | ${(r?.u || n.u || '').slice(0, 70)}`);
    if (r?.g?.length) console.log('       ', r.g.slice(0, 3).map((u) => u.slice(0, 90)).join(' | '));
  }
  const total = comLink.length + google.length;
  console.log(`\nLidas: ${ok}/${total}; com foto: ${fotos}; com texto: ${textos}`);
})();
