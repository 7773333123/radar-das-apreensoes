// /api/foto?i=<id>: foto principal da matéria original (miniatura das listas para notícias ainda
// sem foto). Redireciona para a imagem do veículo; cache de 7 dias na Vercel.
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
  try {
    if (!item || item.sf) throw new Error('id');  // sf: a foto da fonte tem marca d'água
    if (item.img) { res.statusCode = 302; res.setHeader('Location', item.img); res.setHeader('Cache-Control', 'public, s-maxage=604800'); return res.end(); }
    const r = await lerNoticia(item, item.u);
    if (!r || !r.img) throw new Error('sem foto');
    res.statusCode = 302;
    res.setHeader('Location', r.img);
    res.setHeader('Cache-Control', 'public, max-age=86400, s-maxage=604800, stale-while-revalidate=86400');
    return res.end();
  } catch {
    res.statusCode = 404;
    res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=86400');
    return res.end();
  }
};
