// /sitemap.xml gerado a partir do feed: páginas fixas, estados, cidades, tipos, relatórios e notícias.
const { carregar, dados, urlNoticia, indexavel, meses, SLUG_CAT, ESTADOS, cidades, urlCidade } = require('./pagina.js');

const SITE = 'https://www.radardasapreensoes.com.br';
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));

// /sitemap-noticias.xml: sitemap de notícias do Google (só as das últimas 48 horas, até 1.000).
function sitemapNoticias(feed) {
  const limite = Date.now() - 48 * 3600e3;
  const data = (n) => new Date(n.d.length === 16 ? n.d + 'Z' : n.d);
  const itens = feed.noticias.filter((n) => n.d && indexavel(n) && data(n).getTime() >= limite && data(n).getTime() <= Date.now() + 3600e3)
    .slice(0, 1000);
  return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" ' +
    'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n' +
    itens.map((n) => `<url><loc>${esc(SITE + urlNoticia(n))}</loc><news:news><news:publication><news:name>Radar das Apreensões</news:name>` +
      `<news:language>pt</news:language></news:publication><news:publication_date>${data(n).toISOString()}</news:publication_date>` +
      `<news:title>${esc(n.t)}</news:title></news:news></url>`).join('\n') + '\n</urlset>\n';
}

module.exports = async (req, res) => {
  await carregar(req);
  if (new URL(req.url, SITE).searchParams.get('tipo') === 'noticias') {
    res.setHeader('Content-Type', 'application/xml; charset=utf-8');
    res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=600');
    return res.end(sitemapNoticias(dados().feed));
  }
  const { feed } = dados();
  const hoje = new Date().toISOString().slice(0, 10);
  const urls = [
    ['/', hoje, 'hourly'], ['/observatorio', hoje, 'daily'], ['/relatorios', hoje, 'daily'],
    ['/sobre', '', 'monthly'], ['/termos', '', 'yearly'], ['/privacidade', '', 'yearly'], ['/remocao', '', 'yearly'],
    ...Object.keys(ESTADOS).map((uf) => [`/estado/${uf}`, hoje, 'hourly']),
    ...cidades().filter(([, , v]) => v >= 3).map(([uf, c]) => [urlCidade(uf, c), hoje, 'daily']),
    ...SLUG_CAT.slice(0, 8).map((s) => [`/categoria/${s}`, hoje, 'hourly']),
    ...meses().filter(([, v]) => v >= 20).map(([ym]) => [`/relatorio/${ym}`, '', 'weekly']),
    ...feed.noticias.filter(indexavel).slice(0, 45000).map((n) => [urlNoticia(n), (n.d || '').slice(0, 10), '']),
  ];
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map(([u, lm, cf]) => `<url><loc>${esc(SITE + u)}</loc>${lm ? `<lastmod>${lm}</lastmod>` : ''}${cf ? `<changefreq>${cf}</changefreq>` : ''}</url>`).join('\n') +
    '\n</urlset>\n';
  res.setHeader('Content-Type', 'application/xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=3600');
  res.end(xml);
};
