// Páginas próprias renderizadas no servidor (para o Google e para compartilhar):
//   /noticia/<i>-<titulo>    /estado/<UF>    /categoria/<tipo>
//   /relatorios              /relatorio/<AAAA-MM>
// Lê feed.json, feed_links.json e det/ empacotados com a função (vercel.json).
const fs = require('fs');
const path = require('path');

const SITE = 'https://radardasapreensoes.com.br';
const RAIZ = process.cwd();
const ESTADOS = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal',
  ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão', MT: 'Mato Grosso', MS: 'Mato Grosso do Sul', MG: 'Minas Gerais',
  PA: 'Pará', PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima', SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
};
const PREP = { AC: 'no', AL: 'em', AP: 'no', AM: 'no', BA: 'na', CE: 'no', DF: 'no', ES: 'no', GO: 'em', MA: 'no', MT: 'em',
  MS: 'em', MG: 'em', PA: 'no', PB: 'na', PR: 'no', PE: 'em', PI: 'no', RJ: 'no', RN: 'no', RS: 'no', RO: 'em', RR: 'em',
  SC: 'em', SP: 'em', SE: 'em', TO: 'no' };
const SLUG_CAT = ['drogas', 'armas', 'contrabando', 'veiculos', 'dinheiro', 'ambientais', 'medicamentos', 'patrimoniais', 'outras'];
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const MATERIAIS = [['coc', 'Cocaína', 'kg'], ['mac', 'Maconha', 'kg'], ['skh', 'Skunk e haxixe', 'kg'], ['cra', 'Crack', 'kg'],
  ['arm', 'Armas de fogo', 'un'], ['mun', 'Munições', 'un']];

// ---------- dados (em memória enquanto a função estiver aquecida) ----------
let cache = null;
function dados() {
  const arq = path.join(RAIZ, 'feed.json');
  const mtime = fs.statSync(arq).mtimeMs;
  if (cache && cache.mtime === mtime) return cache;
  const feed = JSON.parse(fs.readFileSync(arq, 'utf8'));
  const porI = new Map(feed.noticias.map((n) => [n.i, n]));
  cache = { mtime, feed, porI, links: null, det: new Map() };
  return cache;
}
function links() {
  const c = dados();
  if (!c.links) {
    try { c.links = JSON.parse(fs.readFileSync(path.join(RAIZ, 'feed_links.json'), 'utf8')); } catch { c.links = []; }
  }
  return c.links;
}
function detalhe(i) {
  const c = dados();
  const lote = Math.floor(i / 100);
  if (!c.det.has(lote)) {
    try { c.det.set(lote, JSON.parse(fs.readFileSync(path.join(RAIZ, 'det', `${lote}.json`), 'utf8'))); } catch { c.det.set(lote, {}); }
  }
  return c.det.get(lote)[String(i)] || {};
}

// ---------- utilidades ----------
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const urlOk = (v) => { try { const u = new URL(v); return /^https?:$/.test(u.protocol) ? u.href : ''; } catch { return ''; } };
const slug = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').split('-').slice(0, 12).join('-');
const urlNoticia = (n) => `/noticia/${n.i}-${slug(n.t)}`;
const data = (n) => (n.d ? new Date(n.d.length === 16 ? n.d + 'Z' : n.d) : null);
const fmtData = (d, hora = false) => (d ? d.toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', day: 'numeric', month: 'long', year: 'numeric',
  ...(hora ? { hour: '2-digit', minute: '2-digit' } : {}) }) : '');
const num = (v, casas = 0) => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: casas });
const qtd = (v, u) => (u === 'kg' ? (v >= 1000 ? `${num(v / 1000, 1)} t` : `${num(v, v < 10 ? 1 : 0)} kg`) : num(v));
const corta = (t, n) => (t.length > n ? t.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : t);
const paragrafos = (t) => String(t || '').split(/\n{2,}/).filter((p) => p.trim()).map((p) => `<p class="reader-text">${esc(p.trim())}</p>`).join('');

function cabecalho(atual) {
  const nav = [['/', 'Notícias'], ['/observatorio', 'Observatório'], ['/relatorios', 'Relatórios'], ['/dados', 'Dados abertos']];
  return `<a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header class="masthead"><div class="wrap brandbar">
<a class="brand" href="/" aria-label="Radar das Apreensões — página inicial"><svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" stroke-width="2.6"/><circle cx="16" cy="16" r="7" fill="none" stroke="currentColor" stroke-width="2.6" opacity=".55"/><circle cx="16" cy="16" r="2.6" fill="currentColor"/><path d="M16 16 L27 8" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>
<span class="brand-name">Radar das Apreensões<small>Notícias · Dados · Observatório</small></span></a>
<nav class="mainnav" aria-label="Seções do site">${nav.map(([h, t]) => `<a href="${h}"${t === atual ? ' aria-current="page"' : ''}>${t}</a>`).join('')}</nav>
<form class="searchbox" action="/" method="get" role="search" id="formBuscaPagina"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
<label class="sr" for="buscaTopo">Pesquisar notícias</label><input type="search" id="buscaTopo" name="q" placeholder="Buscar: fuzil, PRF, Manaus…" autocomplete="off" enterkeyhint="search"></form>
</div><nav class="wrap sections" aria-label="Tipos de apreensão">${dados().feed.categorias.slice(0, 8).map((c, k) =>
    `<a href="/categoria/${SLUG_CAT[k]}">${esc(c)}</a>`).join('')}</nav></header>`;
}
const RODAPE = `<footer class="footer"><div class="wrap cols">
<div><h4>Radar das Apreensões</h4><p>Central de notícias e observatório de dados sobre apreensões no Brasil, a partir de mais de mil veículos e órgãos públicos.</p><p>O conteúdo das reportagens pertence aos veículos de origem; cada notícia leva à fonte original.</p></div>
<div><h4>Navegue</h4><p><a href="/observatorio">Observatório</a> · <a href="/relatorios">Relatórios mensais</a></p><p><a href="/dados">Dados abertos e metodologia</a></p><p><a href="/sobre">Sobre e expediente</a></p></div>
<div><h4>Transparência</h4><p><a href="/termos">Termos de uso</a> · <a href="/privacidade">Privacidade</a></p><p><a href="/remocao">Correções e pedidos de remoção</a></p>
<p><button type="button" class="theme-toggle" id="tema">Alternar tema claro/escuro</button></p></div>
</div></footer>`;

function pagina({ titulo, descricao, canonico, imagem, atual, corpo, jsonld, indexar = true }) {
  const og = urlOk(imagem) || `${SITE}/img/og.png`;
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(titulo)}</title><meta name="description" content="${esc(descricao)}"><link rel="canonical" href="${SITE}${canonico}">
${indexar ? '' : '<meta name="robots" content="noindex">'}
<meta property="og:type" content="${jsonld && jsonld['@type'] === 'NewsArticle' ? 'article' : 'website'}"><meta property="og:site_name" content="Radar das Apreensões">
<meta property="og:title" content="${esc(titulo)}"><meta property="og:description" content="${esc(descricao)}"><meta property="og:url" content="${SITE}${canonico}">
<meta property="og:image" content="${esc(og)}"><meta property="og:locale" content="pt_BR"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff"><link rel="icon" href="/img/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/assets/fonts/source-serif-4.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="/assets/radar.css">
${jsonld ? `<script type="application/ld+json">${JSON.stringify(jsonld).replace(/</g, '\\u003c')}</script>` : ''}
<script type="module" src="/assets/pagina.js"></script></head>
<body data-pagina="estatica">${cabecalho(atual)}<main id="conteudo" class="wrap" tabindex="-1">${corpo}</main>${RODAPE}</body></html>`;
}

function kicker(n, cats) {
  const c = (n.c || [])[0];
  return `<div class="kicker">${c != null ? `<a href="/categoria/${SLUG_CAT[c]}">${esc(cats[c])}</a>` : 'Em classificação'}` +
    `${n.uf ? ` · <a class="uf" href="/estado/${n.uf}">${esc(ESTADOS[n.uf])}</a>` : ''}</div>`;
}
function itemLista(n, cats) {
  const foto = urlOk(n.img);
  return `<li><a class="story" href="${urlNoticia(n)}"><div>${kicker({ ...n, c: n.c }, cats).replace(/<a [^>]*>|<\/a>/g, '')}` +
    `<h3 class="headline">${esc(n.t)}</h3><div class="meta">${esc(fmtData(data(n)))} · ${esc(n.f || '')}` +
    `${n.o && n.o.length ? ` · <span class="sources">+${n.o.length} ${n.o.length === 1 ? 'fonte' : 'fontes'}</span>` : ''}</div></div>` +
    `${foto ? `<div class="media"><img src="${esc(foto)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"></div>` : ''}</a></li>`;
}
const lista = (itens, cats) => `<ol class="news">${itens.map((n) => itemLista(n, cats)).join('')}</ol>`;

function somar(itens) {
  const s = {};
  for (const n of itens) for (const [k, v] of Object.entries(n.q || {})) s[k] = (s[k] || 0) + v;
  return s;
}
function kpis(itens) {
  const s = somar(itens);
  const linhas = [['Notícias', num(itens.length)],
    ['Cocaína', qtd(s.coc || 0, 'kg')], ['Maconha e skunk', qtd((s.mac || 0) + (s.skh || 0), 'kg')],
    ['Armas de fogo', num(s.arm || 0)], ['Munições', num(s.mun || 0)],
    ['Veículos de imprensa', num(new Set(itens.flatMap((n) => [n.f, ...(n.o || []).map((o) => o[0])]).filter(Boolean)).size)]];
  return `<dl class="kpis kpis-4">${linhas.map(([k, v]) => `<div class="kpi"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;
}

// ---------- páginas ----------
function paginaNoticia(i) {
  const { feed, porI } = dados();
  const n = porI.get(i);
  if (!n) return null;
  const cats = feed.categorias;
  const t = detalhe(i);
  const url = urlOk(n.u) || urlOk(links()[i] || '');
  const d = data(n);
  const fotos = (Array.isArray(t.g) && t.g.length ? t.g : [n.img]).map(urlOk).filter(Boolean);
  const f = t.f || {};
  const ficha = [
    ['Apreendido', (f.apreendido || []).join(', ')],
    ['Onde', [(f.cidades || []).join(', ') || ESTADOS[n.uf] || '', f.rodovia ? `rodovia ${f.rodovia}` : ''].filter(Boolean).join(' · ')],
    ['Quem atuou', (f.orgaos || []).join(', ')],
    ['Presos', f.presos ? `${num(f.presos)} ${f.presos === 1 ? 'pessoa' : 'pessoas'}` : (f.presos_texto ? 'Sim, segundo a reportagem' : '')],
    ['Mandados', f.mandados || ''], ['Operação', f.operacao || ''], ['Valores citados', f.valor || ''],
    ['Publicado em', fmtData(d, true)],
    ['Fonte', (n.f || '') + (n.o && n.o.length ? ` (também em ${n.o.map((o) => o[0]).join(', ')})` : '')],
  ].filter(([, v]) => v);
  let fonte = '';
  if (Array.isArray(t.p) && t.p.length) {
    fonte = `<h2>Texto completo</h2>${t.p.map((p) => `<p class="reader-text">${esc(p)}</p>`).join('')}` +
      `<p class="reader-note">${t.l === 'oficial' ? `Comunicado oficial publicado por ${esc(n.f)}, reproduzido na íntegra com crédito.`
        : `Texto reproduzido integralmente de ${esc(n.f)}, sob a licença ${esc(t.l)}, que permite a reprodução com crédito.`}</p>`;
  } else {
    const trecho = t.tr && t.tr.length > (n.r || '').length ? t.tr : n.r;
    if (trecho) {
      fonte = `<h2>O que diz a fonte</h2><blockquote class="reader-quote">${paragrafos(trecho)}</blockquote>` +
        `<p class="reader-note">${t.tr ? 'Abertura da reportagem publicada' : 'Resumo publicado'} por ${esc(n.f)}, reproduzido com crédito.` +
        `${url ? ` A reportagem continua no site de origem: <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">ler a íntegra ↗</a>` : ''}</p>`;
    }
  }
  // Relacionadas: mesmo estado e tipo, mais próximas no tempo.
  const relacionadas = feed.noticias.filter((x) => x.i !== i && x.uf && x.uf === n.uf && (x.c || [])[0] === (n.c || [])[0])
    .sort((a, b) => Math.abs(data(a) - d) - Math.abs(data(b) - d)).slice(0, 6);
  const descricao = corta((t.s || n.r || n.t).split('\n')[0], 160);
  const corpo = `<article class="artigo">${kicker(n, cats)}<h1 class="art-titulo">${esc(n.t)}</h1>
<div class="meta">${esc(fmtData(d, true))} · ${esc(n.f || '')}${url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">ver original ↗</a>` : ''}</div>
${fotos.length ? `<div class="art-fotos">${fotos.map((src, k) => `<img src="${esc(src)}" alt="${k ? '' : esc(n.t)}" ${k ? 'loading="lazy"' : 'fetchpriority="high"'} decoding="async" referrerpolicy="no-referrer">`).join('')}</div>
${fotos.length > 1 ? `<p class="reader-note">${fotos.length} fotos · deslize para ver todas. Imagens: ${esc(n.f)}.</p>` : `<p class="reader-note">Imagem: ${esc(n.f)}.</p>`}` : ''}
${t.s ? `<h2>Resumo do Radar</h2>${paragrafos(t.s)}` : ''}
${ficha.length ? `<section class="facts"><h2>Principais informações</h2><dl>${ficha.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></section>` : ''}
${fonte}
${n.o && n.o.length ? `<p class="reader-note">Também noticiado por: ${n.o.map(([fo, u]) => (urlOk(u) ? `<a href="${esc(urlOk(u))}" target="_blank" rel="noopener noreferrer">${esc(fo)}</a>` : esc(fo))).join(', ')}.</p>` : ''}
</article>
${relacionadas.length ? `<div class="section-head"><h2>Mais de ${esc(cats[(n.c || [8])[0]])} ${n.uf ? `${PREP[n.uf]} ${esc(ESTADOS[n.uf])}` : ''}</h2><a href="/estado/${n.uf}">Ver o estado →</a></div>${lista(relacionadas, cats)}` : ''}`;
  const jsonld = {
    '@context': 'https://schema.org', '@type': 'NewsArticle', headline: corta(n.t, 110), datePublished: d ? d.toISOString() : undefined,
    image: fotos.slice(0, 3), description: descricao, mainEntityOfPage: `${SITE}${urlNoticia(n)}`,
    isBasedOn: url || undefined, author: { '@type': 'Organization', name: n.f || 'Radar das Apreensões' },
    publisher: { '@type': 'Organization', name: 'Radar das Apreensões', logo: { '@type': 'ImageObject', url: `${SITE}/img/og.png` } },
  };
  return { html: pagina({ titulo: `${corta(n.t, 90)} | Radar das Apreensões`, descricao, canonico: urlNoticia(n), imagem: fotos[0], atual: 'Notícias', corpo, jsonld }), canonico: urlNoticia(n) };
}

function paginaLista({ titulo, h1, intro, itens, canonico, atual, rodape = '' }) {
  const { feed } = dados();
  const agora = Date.now();
  const r30 = itens.filter((n) => data(n) && agora - data(n) <= 30 * 864e5);
  const r365 = itens.filter((n) => data(n) && agora - data(n) <= 365 * 864e5);
  const recentes = [...itens].sort((a, b) => (b.d || '').localeCompare(a.d || '')).slice(0, 60);
  const corpo = `<header class="pg-head"><h1 class="art-titulo">${esc(h1)}</h1><p class="dek">${esc(intro)}</p></header>
<div class="duas"><section class="panel"><h3>Últimos 30 dias</h3>${kpis(r30)}</section><section class="panel"><h3>Últimos 12 meses</h3>${kpis(r365)}</section></div>
<p class="note">Quantidades citadas nas notícias, sem duplicatas. Não são estatísticas oficiais.</p>
<div class="section-head"><h2>Notícias mais recentes</h2><span class="count">${num(itens.length)} no acervo</span></div>${lista(recentes, feed.categorias)}${rodape}`;
  return pagina({ titulo: `${titulo} | Radar das Apreensões`, descricao: intro, canonico, atual, corpo });
}

function paginaEstado(uf) {
  const { feed } = dados();
  if (!ESTADOS[uf]) return null;
  const itens = feed.noticias.filter((n) => n.uf === uf);
  const nome = ESTADOS[uf];
  return { html: paginaLista({
    titulo: `Apreensões ${PREP[uf]} ${nome}`, h1: `Apreensões ${PREP[uf]} ${nome}`, canonico: `/estado/${uf}`, atual: 'Notícias', itens,
    intro: `Notícias de apreensões de drogas, armas, contrabando e outros bens ${PREP[uf]} ${nome}, reunidas de veículos de imprensa e órgãos públicos e atualizadas o dia todo.`,
    rodape: `<p class="more"><a class="btn ghost" href="/#uf=${uf}">Ver todas e filtrar</a> <a class="btn ghost" href="/observatorio#uf=${uf}">Abrir no Observatório</a></p>`,
  }), canonico: `/estado/${uf}` };
}

function paginaCategoria(s) {
  const { feed } = dados();
  const c = SLUG_CAT.indexOf(s);
  if (c < 0) return null;
  const itens = feed.noticias.filter((n) => (n.c || []).includes(c));
  const nome = feed.categorias[c];
  return { html: paginaLista({
    titulo: `${nome}: apreensões no Brasil`, h1: nome, canonico: `/categoria/${s}`, atual: 'Notícias', itens,
    intro: `Notícias de apreensões de ${nome.toLowerCase()} em todo o Brasil, por estado e período, atualizadas o dia todo.`,
    rodape: `<p class="more"><a class="btn ghost" href="/#cat=${c}">Ver todas e filtrar</a> <a class="btn ghost" href="/observatorio#cat=${c}">Abrir no Observatório</a></p>`,
  }), canonico: `/categoria/${s}` };
}

function meses() {
  const { feed } = dados();
  const m = new Map();
  for (const n of feed.noticias) if (n.d && n.d >= '2006') m.set(n.d.slice(0, 7), (m.get(n.d.slice(0, 7)) || 0) + 1);
  return [...m].sort((a, b) => b[0].localeCompare(a[0]));
}
const nomeMes = (ym) => `${MESES[Number(ym.slice(5, 7)) - 1]} de ${ym.slice(0, 4)}`;

function paginaRelatorios() {
  const lista = meses().filter(([, v]) => v >= 20);
  const anos = new Map();
  for (const [ym, v] of lista) { const a = ym.slice(0, 4); if (!anos.has(a)) anos.set(a, []); anos.get(a).push([ym, v]); }
  const corpo = `<header class="pg-head"><h1 class="art-titulo">Relatórios mensais</h1><p class="dek">Para cada mês: total de notícias, estados e tipos mais frequentes, quantidades citadas e as maiores apreensões noticiadas. Gerados automaticamente a partir do acervo, sem duplicatas.</p></header>
${[...anos].map(([a, ms]) => `<div class="section-head"><h2>${a}</h2></div><ul class="meses">${ms.map(([ym, v]) =>
    `<li><a href="/relatorio/${ym}"><strong>${esc(nomeMes(ym))}</strong><span>${num(v)} notícias</span></a></li>`).join('')}</ul>`).join('')}`;
  return { html: pagina({ titulo: 'Relatórios mensais de apreensões | Radar das Apreensões', descricao: 'Relatórios mensais automáticos das apreensões noticiadas no Brasil: rankings por estado, tipos e maiores apreensões.', canonico: '/relatorios', atual: 'Relatórios', corpo }), canonico: '/relatorios' };
}

function paginaRelatorio(ym) {
  const { feed } = dados();
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(ym)) return null;
  const itens = feed.noticias.filter((n) => n.d && n.d.startsWith(ym));
  if (!itens.length) return null;
  const cats = feed.categorias;
  const porUf = {}, porCat = {};
  for (const n of itens) { if (n.uf) porUf[n.uf] = (porUf[n.uf] || 0) + 1; for (const c of n.c || []) porCat[c] = (porCat[c] || 0) + 1; }
  const topUf = Object.entries(porUf).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const topCat = Object.entries(porCat).sort((a, b) => b[1] - a[1]);
  const maiores = MATERIAIS.map(([k, nome, u]) => [nome, u, itens.filter((n) => n.q && n.q[k]).sort((a, b) => b.q[k] - a.q[k]).slice(0, 5).map((n) => [n, n.q[k]])])
    .filter(([, , l]) => l.length);
  const repercutidas = itens.filter((n) => n.o && n.o.length).sort((a, b) => b.o.length - a.o.length).slice(0, 8);
  const [ano, mes] = ym.split('-').map(Number);
  const ant = `${mes === 1 ? ano - 1 : ano}-${String(mes === 1 ? 12 : mes - 1).padStart(2, '0')}`;
  const prox = `${mes === 12 ? ano + 1 : ano}-${String(mes === 12 ? 1 : mes + 1).padStart(2, '0')}`;
  const existe = new Set(meses().map(([m]) => m));
  const barra = (pares, max, rotulo) => `<ol class="barras">${pares.map(([k, v]) =>
    `<li><span class="rot">${rotulo(k)}</span><span class="bar"><i style="width:${Math.max(2, (v / max) * 100).toFixed(1)}%"></i></span><span class="val">${num(v)}</span></li>`).join('')}</ol>`;
  const corpo = `<header class="pg-head"><p class="kicker">Relatório mensal</p><h1 class="art-titulo">Apreensões noticiadas em ${esc(nomeMes(ym))}</h1>
<p class="dek">${num(itens.length)} notícias de apreensões no Brasil, sem duplicatas${topUf[0] ? `; ${esc(ESTADOS[topUf[0][0]])} foi o estado com mais registros (${num(topUf[0][1])})` : ''}${topCat[0] ? ` e ${esc(cats[topCat[0][0]].toLowerCase())} o tipo mais frequente (${num(topCat[0][1])})` : ''}.</p></header>
${kpis(itens)}<p class="note">Quantidades citadas nas notícias, sem duplicatas. Não são estatísticas oficiais.</p>
<div class="duas"><section class="panel"><h3>Estados com mais notícias</h3>${barra(topUf, topUf[0] ? topUf[0][1] : 1, (uf) => `<a href="/estado/${uf}">${esc(ESTADOS[uf])}</a>`)}</section>
<section class="panel"><h3>Tipos de apreensão</h3>${barra(topCat, topCat[0] ? topCat[0][1] : 1, (c) => `<a href="/categoria/${SLUG_CAT[c]}">${esc(cats[c])}</a>`)}</section></div>
${maiores.length ? `<div class="section-head"><h2>Maiores apreensões noticiadas</h2></div><div class="duas">${maiores.map(([nome, u, l]) =>
    `<section class="panel"><h3>${esc(nome)}</h3><ol class="top">${l.map(([n, v]) => `<li><strong>${esc(qtd(v, u))}</strong> <a href="${urlNoticia(n)}">${esc(n.t)}</a> <span class="meta">${esc(fmtData(data(n)))}${n.uf ? ' · ' + n.uf : ''}</span></li>`).join('')}</ol></section>`).join('')}</div>` : ''}
${repercutidas.length ? `<div class="section-head"><h2>Mais repercutidas</h2></div>${lista(repercutidas, cats)}` : ''}
<p class="more">${existe.has(ant) ? `<a class="btn ghost" href="/relatorio/${ant}">← ${esc(nomeMes(ant))}</a>` : ''} <a class="btn ghost" href="/relatorios">Todos os relatórios</a> ${existe.has(prox) ? `<a class="btn ghost" href="/relatorio/${prox}">${esc(nomeMes(prox))} →</a>` : ''}</p>`;
  return { html: pagina({ titulo: `Apreensões em ${nomeMes(ym)}: relatório mensal | Radar das Apreensões`,
    descricao: `${num(itens.length)} notícias de apreensões no Brasil em ${nomeMes(ym)}: estados, tipos e maiores apreensões noticiadas.`,
    canonico: `/relatorio/${ym}`, atual: 'Relatórios', corpo }), canonico: `/relatorio/${ym}` };
}


// ---------- páginas institucionais ----------
const CONTATO = 'contato@radardasapreensoes.com.br';
const INSTITUCIONAIS = {
  sobre: ['Sobre o Radar e expediente', 'O que é o Radar das Apreensões, como funciona, quem responde pelo site e como entrar em contato.', `
<p class="reader-text">O <strong>Radar das Apreensões</strong> é uma central de notícias e um observatório de dados sobre apreensões no Brasil: drogas, armas e munições, contrabando, veículos, dinheiro, crimes ambientais, medicamentos e bloqueios de bens. Reunimos o que é publicado por mais de mil veículos de imprensa e órgãos públicos, sem duplicatas, organizado por estado, tipo e período.</p>
<h2>Como funciona</h2>
<p class="reader-text">A coleta é automática e roda o dia todo, a cada 20 minutos. Cada notícia passa por regras próprias que decidem se ela trata de uma apreensão e de qual tipo, identificam o estado, agrupam as versões da mesma notícia publicadas por veículos diferentes e extraem os fatos principais (o que foi apreendido, quanto, onde, quem atuou). O detalhamento está em <a href="/dados#metodologia">Dados abertos e metodologia</a>.</p>
<h2>O que publicamos</h2>
<p class="reader-text">Para cada notícia: título, data, fonte, foto com crédito, um resumo redigido pelo Radar a partir dos fatos, a ficha de informações e um trecho de abertura da reportagem, sempre com link para a íntegra no site de origem. Comunicados oficiais de órgãos públicos e textos com licença aberta são reproduzidos na íntegra, com crédito. O conteúdo das reportagens pertence aos veículos que as publicaram.</p>
<h2>O que não somos</h2>
<p class="reader-text">Não somos órgão público nem fonte oficial de estatísticas. Os números do site são quantidades citadas nas notícias; servem para acompanhar tendências, não substituem os dados oficiais das secretarias de segurança e das polícias.</p>
<h2>Expediente</h2>
<p class="reader-text">Radar das Apreensões · radardasapreensoes.com.br<br>Contato, correções e parcerias: <a href="mailto:${CONTATO}">${CONTATO}</a></p>
<p class="reader-text">Veículos que desejem autorizar a reprodução integral das suas reportagens, com crédito e link, podem escrever para o mesmo endereço.</p>`],
  termos: ['Termos de uso', 'Condições de uso do Radar das Apreensões, dos seus dados e do conteúdo de terceiros.', `
<p class="reader-note">Última atualização: novembro de 2026.</p>
<h2>1. O serviço</h2><p class="reader-text">O Radar das Apreensões reúne e organiza notícias públicas sobre apreensões no Brasil e produz indicadores a partir delas. O uso do site é gratuito e não exige cadastro.</p>
<h2>2. Conteúdo de terceiros</h2><p class="reader-text">Títulos, fotos, trechos e textos das reportagens pertencem aos veículos e órgãos que os publicaram e são exibidos com crédito e link para a fonte, nos limites da Lei 9.610/1998 (citação com indicação de autoria) ou da licença do próprio conteúdo. Para reutilizar esse material, procure o titular dos direitos.</p>
<h2>3. Conteúdo do Radar e dados abertos</h2><p class="reader-text">Os resumos, fichas, indicadores e arquivos da seção <a href="/dados">Dados abertos</a> podem ser reutilizados, inclusive comercialmente, desde que citada a fonte: "Radar das Apreensões".</p>
<h2>4. Precisão das informações</h2><p class="reader-text">A coleta e a classificação são automáticas e podem conter erros. As notícias refletem o que foi publicado na data, e pessoas citadas como suspeitas são presumidas inocentes até decisão judicial definitiva. Encontrou um erro? Use a página de <a href="/remocao">correções e pedidos de remoção</a>.</p>
<h2>5. Uso proibido</h2><p class="reader-text">É proibido usar o site para assediar, expor ou ameaçar pessoas citadas nas notícias, sobrecarregar os servidores com acessos automatizados abusivos ou apresentar os dados como estatística oficial.</p>
<h2>6. Responsabilidade</h2><p class="reader-text">O Radar não se responsabiliza pelo conteúdo dos sites de origem nem por decisões tomadas apenas com base nas informações aqui reunidas.</p>
<h2>7. Contato</h2><p class="reader-text"><a href="mailto:${CONTATO}">${CONTATO}</a></p>`],
  privacidade: ['Política de privacidade', 'Como o Radar das Apreensões trata dados pessoais, conforme a LGPD.', `
<p class="reader-note">Última atualização: novembro de 2026. Lei Geral de Proteção de Dados (Lei 13.709/2018).</p>
<h2>Dados de quem visita o site</h2><p class="reader-text">O site não tem cadastro, não usa cookies de publicidade nem ferramentas de rastreamento. A preferência de tema (claro ou escuro) fica guardada só no seu navegador. A hospedagem (Vercel) registra dados técnicos de acesso, como endereço IP e navegador, por segurança e prevenção de abusos, pelo prazo definido pelo provedor.</p>
<h2>Dados pessoais nas notícias</h2><p class="reader-text">As notícias podem citar nomes de pessoas presas, suspeitas ou investigadas, tal como publicados pela imprensa e por órgãos públicos. Esses dados são tratados com base no interesse público e na liberdade de informação jornalística (art. 4º, II, "a", da LGPD), e o Radar não os enriquece, cruza nem os usa para outra finalidade.</p>
<h2>Seus direitos</h2><p class="reader-text">Se você é citado em uma notícia, pode pedir correção, atualização (por exemplo, absolvição ou arquivamento) ou a desindexação do seu nome. Veja a página de <a href="/remocao">correções e pedidos de remoção</a>.</p>
<h2>Contato do controlador</h2><p class="reader-text"><a href="mailto:${CONTATO}">${CONTATO}</a></p>`],
  remocao: ['Correções e pedidos de remoção', 'Como pedir correção, atualização ou remoção de uma notícia do Radar das Apreensões.', `
<p class="reader-text">O Radar reúne notícias publicadas por terceiros, mas responde pelo que exibe. Atendemos pedidos de:</p>
<ul class="lista-texto"><li><strong>Correção</strong>: dado errado no resumo, na ficha, no estado ou no tipo da notícia.</li>
<li><strong>Atualização</strong>: a pessoa citada foi absolvida, o caso foi arquivado ou a notícia original foi corrigida.</li>
<li><strong>Remoção ou desindexação</strong>: dados pessoais expostos sem interesse público, pedido do titular com base na LGPD ou ordem judicial.</li>
<li><strong>Direitos autorais</strong>: o titular de uma reportagem ou foto que prefira não ser exibido.</li></ul>
<h2>Como pedir</h2><p class="reader-text">Envie um e-mail para <a href="mailto:${CONTATO}?subject=Pedido%20de%20corre%C3%A7%C3%A3o%20ou%20remo%C3%A7%C3%A3o">${CONTATO}</a> com o endereço da notícia no Radar, o que deve ser corrigido ou removido e, se for o caso, o documento que comprova (decisão judicial, certidão, matéria corrigida). Respondemos em até 5 dias úteis; pedidos de direitos autorais e ordens judiciais são atendidos com prioridade.</p>`],
};
function paginaInstitucional(nome) {
  const p = INSTITUCIONAIS[nome];
  if (!p) return null;
  const [titulo, descricao, corpo] = p;
  return { html: pagina({ titulo: `${titulo} | Radar das Apreensões`, descricao, canonico: `/${nome}`, atual: '',
    corpo: `<article class="artigo"><h1 class="art-titulo">${titulo}</h1>${corpo}</article>` }), canonico: `/${nome}` };
}

function naoEncontrada() {
  return pagina({ titulo: 'Página não encontrada | Radar das Apreensões', descricao: 'Página não encontrada.', canonico: '/', atual: '', indexar: false,
    corpo: '<header class="pg-head"><h1 class="art-titulo">Página não encontrada</h1><p class="dek">O endereço pode ter mudado. <a href="/">Voltar às notícias</a>.</p></header>' });
}

module.exports = (req, res) => {
  const u = new URL(req.url, SITE);
  const tipo = u.searchParams.get('tipo');
  const id = u.searchParams.get('id') || '';
  let r = null;
  try {
    if (tipo === 'noticia') r = paginaNoticia(Number((id.match(/^\d+/) || [''])[0]));
    else if (tipo === 'estado') r = paginaEstado(id.toUpperCase());
    else if (tipo === 'categoria') r = paginaCategoria(id.toLowerCase());
    else if (tipo === 'relatorios') r = paginaRelatorios();
    else if (tipo === 'relatorio') r = paginaRelatorio(id);
    else if (tipo === 'institucional') r = paginaInstitucional(id);
  } catch (e) {
    console.error(e);
    res.statusCode = 500;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    return res.end('Erro ao montar a página.');
  }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  if (!r) { res.statusCode = 404; res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=300'); return res.end(naoEncontrada()); }
  // Endereço sem o título (ou com título antigo): redireciona para o canônico.
  if (tipo === 'noticia' && u.searchParams.get('caminho') !== r.canonico.slice('/noticia/'.length)) {
    res.statusCode = 301; res.setHeader('Location', r.canonico); return res.end();
  }
  res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=600, stale-while-revalidate=3600');
  res.end(r.html);
};
module.exports.dados = dados;
module.exports.urlNoticia = urlNoticia;
module.exports.meses = meses;
module.exports.SLUG_CAT = SLUG_CAT;
module.exports.ESTADOS = ESTADOS;
