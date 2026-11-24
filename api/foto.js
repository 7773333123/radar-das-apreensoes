// /api/foto?i=<id>: foto principal da matéria original (miniatura das listas para notícias ainda
// sem foto). Redireciona para a imagem do veículo; cache de 7 dias na Vercel.
const { carregar, noticiaCompleta } = require('./pagina.js');
const { lerNoticia } = require('./_extrair.js');

module.exports = async (req, res) => {
  const i = Number(new URL(req.url, 'https://x').searchParams.get('i'));
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
