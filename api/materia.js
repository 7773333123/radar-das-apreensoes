// /api/materia?i=<id>: lê na hora a matéria original de uma notícia do Radar (fotos, trecho ou texto
// oficial) quando ela ainda não passou pela leitura em lote. Só aceita ids do feed (nunca uma URL
// qualquer); a resposta fica no cache da Vercel por 7 dias.
const { dados, links } = require('./pagina.js');
const { lerNoticia } = require('./_extrair.js');

module.exports = async (req, res) => {
  const i = Number(new URL(req.url, 'https://x').searchParams.get('i'));
  const { feed } = dados();
  const item = Number.isFinite(i) && (feed._porId ||= new Map(feed.noticias.map((n) => [n.i, n]))).get(i);
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (!item) { res.statusCode = 404; res.setHeader('Cache-Control', 'public, s-maxage=3600'); return res.end('{}'); }
  try {
    const r = await lerNoticia(item, links()[i]);
    if (!r || (!r.img && !r.tr && !r.p)) throw new Error('nada encontrado');
    res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=604800, stale-while-revalidate=86400');
    return res.end(JSON.stringify(r));
  } catch (e) {
    res.statusCode = 404;
    res.setHeader('Cache-Control', 'public, s-maxage=21600');  // tenta de novo em 6 h
    return res.end(JSON.stringify({ erro: String(e.message || e).slice(0, 80) }));
  }
};
