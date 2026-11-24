// /api/materia?i=<id>: lê na hora a matéria original de uma notícia do Radar (fotos, trecho ou texto
// oficial) quando ela ainda não passou pela leitura em lote. Só aceita ids do feed (nunca uma URL
// qualquer); a resposta fica no cache da Vercel por 7 dias.
const { carregar, noticiaCompleta } = require('./pagina.js');
const { lerNoticia } = require('./_extrair.js');

module.exports = async (req, res) => {
  const q = new URL(req.url, 'https://x').searchParams;
  // Segurança (24/11/2026): só ?i=<número>. Parâmetro a mais ou id inválido é recusado (fica no cache),
  // para ninguém furar o cache da Vercel e gastar o servidor com milhares de endereços diferentes.
  if ([...q.keys()].some((k) => k !== 'i') || !/^\d{1,17}$/.test(q.get('i') || '')) {
    res.statusCode = 400;
    res.setHeader('Cache-Control', 'public, max-age=86400, s-maxage=604800');
    return res.end();
  }
  const i = Number(q.get('i'));
  let item = null;
  try { await carregar(req); item = Number.isFinite(i) && ((await noticiaCompleta(i)) || {}).n; } catch (e) { console.error(e); }
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (!item) { res.statusCode = 404; res.setHeader('Cache-Control', 'public, s-maxage=3600'); return res.end('{}'); }
  try {
    const r = await lerNoticia(item, item.u);
    if (!r || (!r.img && !r.tr && !r.p)) throw new Error('nada encontrado');
    res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400');
    return res.end(JSON.stringify(r));
  } catch (e) {
    res.statusCode = 404;
    res.setHeader('Cache-Control', 'public, s-maxage=21600');  // tenta de novo em 6 h
    return res.end(JSON.stringify({ erro: String(e.message || e).slice(0, 80) }));
  }
};
