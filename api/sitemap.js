// /sitemap.xml gerado a partir do feed: páginas fixas, estados, tipos, relatórios e notícias.
const { dados, urlNoticia, meses, SLUG_CAT, ESTADOS } = require('./pagina.js');

const SITE = 'https://www.radardasapreensoes.com.br';
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c]));

module.exports = (req, res) => {
  const { feed } = dados();
  const hoje = new Date().toISOString().slice(0, 10);
  const urls = [
    ['/', hoje, 'hourly'], ['/observatorio', hoje, 'daily'], ['/relatorios', hoje, 'daily'], ['/dados', hoje, 'daily'],
    ['/sobre', '', 'monthly'], ['/termos', '', 'yearly'], ['/privacidade', '', 'yearly'], ['/remocao', '', 'yearly'],
    ...Object.keys(ESTADOS).map((uf) => [`/estado/${uf}`, hoje, 'hourly']),
    ...SLUG_CAT.slice(0, 8).map((s) => [`/categoria/${s}`, hoje, 'hourly']),
    ...meses().filter(([, v]) => v >= 20).map(([ym]) => [`/relatorio/${ym}`, '', 'weekly']),
    ...feed.noticias.slice(0, 45000).map((n) => [urlNoticia(n), (n.d || '').slice(0, 10), '']),
  ];
  const xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map(([u, lm, cf]) => `<url><loc>${esc(SITE + u)}</loc>${lm ? `<lastmod>${lm}</lastmod>` : ''}${cf ? `<changefreq>${cf}</changefreq>` : ''}</url>`).join('\n') +
    '\n</urlset>\n';
  res.setHeader('Content-Type', 'application/xml; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=3600');
  res.end(xml);
};
