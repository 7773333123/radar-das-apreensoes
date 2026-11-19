// Páginas próprias renderizadas no servidor (para o Google e para compartilhar):
//   /noticia/<i>-<titulo>    /estado/<UF>    /cidade/<UF>/<cidade>    /categoria/<tipo>
//   /relatorios              /relatorio/<AAAA-MM>
// Lê feed.json, feed_links.json e det/ publicados pelo próprio site (por HTTP, com cache).
const fs = require('fs');
const path = require('path');

const SITE = 'https://www.radardasapreensoes.com.br';
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
// As funções não levam cópia dos dados (limite de 250 MB da Vercel): buscam os arquivos
// estáticos já publicados pelo próprio site (/feed.json, /det/<lote>.json, /feed_links.json).
const VALIDADE = 5 * 60e3;
let cache = null;
let carregando = null;
function base(req) {
  if (process.env.RADAR_DADOS_BASE) return process.env.RADAR_DADOS_BASE.replace(/\/$/, '');
  const h = req && req.headers ? String(req.headers['x-forwarded-host'] || req.headers.host || '') : '';
  return /^[a-z0-9.-]+(:\d+)?$/i.test(h) && !/^localhost|^127\./.test(h) ? `https://${h}` : SITE;
}
async function buscarJSON(url, opcoes = {}) {
  const r = await fetch(url, { ...opcoes, signal: AbortSignal.timeout(9000) });
  return r;
}
async function carregar(req) {
  if (cache && Date.now() - cache.t < VALIDADE) return cache;
  if (carregando) return carregando;
  carregando = (async () => {
    const b = base(req);
    try {
      const r = await buscarJSON(`${b}/feed.json`, { headers: cache && cache.etag ? { 'If-None-Match': cache.etag } : {} });
      if (r.status === 304 && cache) { cache.t = Date.now(); return cache; }
      if (!r.ok) throw new Error(`feed.json: HTTP ${r.status}`);
      const feed = await r.json();
      const porI = new Map(feed.noticias.map((n) => [n.i, n]));
      let indice = null;
      try { const ri = await buscarJSON(`${b}/anos/indice.json`); if (ri.ok) indice = await ri.json(); } catch { /* sem índice */ }
      cache = { t: Date.now(), etag: r.headers.get('etag'), base: b, feed, porI, links: null, det: new Map(), indice, anos: new Map(), ids: null };
      return cache;
    } catch (e) {
      if (cache) { cache.t = Date.now() - VALIDADE + 60e3; return cache; }  // usa o que tem; tenta em 1 min
      throw e;
    }
  })().finally(() => { carregando = null; });
  return carregando;
}
function dados() {
  if (!cache) throw new Error('dados ainda não carregados (chame carregar)');
  return cache;
}
async function links() {
  const c = dados();
  if (!c.links) {
    c.links = buscarJSON(`${c.base}/feed_links.json`).then((r) => (r.ok ? r.json() : {})).catch(() => { c.links = null; return {}; });
  }
  return c.links;
}
async function detalhe(i) {
  const c = dados();
  const lote = i % 256; // mesmo LOTES de gerar_feed_site.py
  if (!c.det.has(lote)) {
    if (c.det.size >= 48) c.det.delete(c.det.keys().next().value);  // guarda no máximo 48 lotes
    c.det.set(lote, buscarJSON(`${c.base}/det/${lote}.json`).then((r) => (r.ok ? r.json() : {}))
      .catch(() => { c.det.delete(lote); return {}; }));
  }
  return (await c.det.get(lote))[String(i)] || {};
}
// Anos anteriores ao feed.json (anos/AAAA.json), carregados só quando uma página precisa
// (notícia antiga, relatório de mês antigo). Guarda no máximo 3 anos na memória.
async function anoArquivo(a) {
  const c = dados();
  a = String(a);
  if (!(c.indice?.arquivos || []).includes(a)) return [];
  if (!c.anos.has(a)) {
    if (c.anos.size >= 3) c.anos.delete(c.anos.keys().next().value);
    c.anos.set(a, buscarJSON(`${c.base}/anos/${a}.json`).then((r) => (r.ok ? r.json() : { noticias: [] }))
      .then((d) => { const lista = d.noticias || []; lista._porI = new Map(lista.map((n) => [n.i, n])); return lista; })
      .catch(() => { c.anos.delete(a); return []; }));
  }
  return c.anos.get(a);
}
async function anoDaNoticia(i) {
  const c = dados();
  if (!c.ids) {
    c.ids = buscarJSON(`${c.base}/anos/ids.json`).then((r) => (r.ok ? r.json() : {}))
      .then((d) => { const m = new Map(); for (const [a, lista] of Object.entries(d)) for (const x of lista) m.set(x, a); return m; })
      .catch(() => { c.ids = null; return new Map(); });
  }
  return (await c.ids).get(i);
}
async function buscarNoticia(i) {
  const n = dados().porI.get(i);
  if (n) return n;
  const a = await anoDaNoticia(i);
  return a ? ((await anoArquivo(a))._porI || new Map()).get(i) || null : null;
}
// Notícia com os campos completos (link original, resumo inteiro, links das outras fontes),
// que o feed publicado deixa em det/.
async function noticiaCompleta(i) {
  const n = await buscarNoticia(i);
  if (!n) return null;
  const t = await detalhe(i);
  const c = { ...n };
  if (t.u) c.u = t.u;
  if (t.r) c.r = t.r;
  if (t.o) c.o = t.o;
  if (!c.u) { const l = (await links())[i]; if (l) c.u = l; }
  return { n: c, t };
}

// ---------- utilidades ----------
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const urlOk = (v) => { try { const u = new URL(v); return /^https?:$/.test(u.protocol) ? u.href : ''; } catch { return ''; } };
const slug = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').split('-').slice(0, 12).join('-');
const urlNoticia = (n) => `/noticia/${n.i}-${slug(n.t)}`;
const urlCidade = (uf, cid) => `/cidade/${uf}/${slug(cid)}`;
// Cidades com notícias: [[uf, cidade, quantidade], ...] da maior para a menor.
function cidades() {
  const { feed } = dados();
  if (feed._cidades) return feed._cidades;
  const m = new Map();
  for (const n of feed.noticias) if (n.cid && n.uf) { const k = `${n.uf}|${n.cid}`; m.set(k, (m.get(k) || 0) + 1); }
  feed._cidades = [...m].map(([k, v]) => [...k.split('|'), v]).sort((a, b) => b[2] - a[2]);
  return feed._cidades;
}
// Só vão para o índice do Google as notícias com conteúdo próprio relevante: o
// Google penaliza sites com milhares de páginas parecidas e pouco valor próprio.
const indexavel = (n) => Boolean(n.x || n.q || (n.o && n.o.length) || (n.r && (n.r.length >= 200 || n.r.endsWith('…'))) || n.g);
const data = (n) => (n.d ? new Date(n.d.length === 16 ? n.d + 'Z' : n.d) : null);
const fmtData = (d, hora = false) => (d ? d.toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo', day: 'numeric', month: 'long', year: 'numeric',
  ...(hora ? { hour: '2-digit', minute: '2-digit' } : {}) }) : '');
const num = (v, casas = 0) => Number(v).toLocaleString('pt-BR', { maximumFractionDigits: casas });
const qtd = (v, u) => (u === 'kg' ? (v >= 1000 ? `${num(v / 1000, 1)} t` : `${num(v, v < 10 ? 1 : 0)} kg`) : num(v));
const corta = (t, n) => (t.length > n ? t.slice(0, n - 1).replace(/\s+\S*$/, '') + '…' : t);
const paragrafos = (t) => String(t || '').split(/\n{2,}/).filter((p) => p.trim()).map((p) => `<p class="reader-text">${esc(p.trim())}</p>`).join('');

function cabecalho(atual) {
  const nav = [['/', 'Notícias'], ['/observatorio', 'Observatório'], ['/relatorios', 'Relatórios']];
  return `<a class="skip" href="#conteudo">Pular para o conteúdo</a>
<header class="masthead"><div class="wrap brandbar">
<a class="brand" href="/" aria-label="Radar das Apreensões — página inicial"><svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true"><path d="M32 3C19 3 9 13 9 26c0 17 23 35.5 23 35.5S55 43 55 26C55 13 45 3 32 3z" fill="#b3261e"/><path d="M24.5 40V14.5h9a8 8 0 0 1 0 16h-9" fill="none" stroke="#fff" stroke-width="5.4" stroke-linejoin="round"/><path d="M31.5 30.5l9.5 9.5" stroke="#fff" stroke-width="5.4" stroke-linecap="round"/><path d="M40.5 9.6a11 11 0 0 1 7.9 7.9" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".55"/><path d="M40.6 13.8a6.6 6.6 0 0 1 3.6 3.6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".9"/></svg>
<span class="brand-name"><b>RADAR</b><span>das Apreensões</span></span></a>
<nav class="mainnav" aria-label="Seções do site">${nav.map(([h, t]) => `<a href="${h}"${t === atual ? ' aria-current="page"' : ''}>${t}</a>`).join('')}</nav>
<form class="searchbox" action="/" method="get" role="search" id="formBuscaPagina"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
<label class="sr" for="buscaTopo">Pesquisar notícias</label><input type="search" id="buscaTopo" name="q" placeholder="Buscar" autocomplete="off" enterkeyhint="search"></form>
</div><nav class="wrap sections" aria-label="Tipos de apreensão">${dados().feed.categorias.slice(0, 8).map((c, k) =>
    `<a href="/categoria/${SLUG_CAT[k]}">${esc(c)}</a>`).join('')}</nav></header>`;
}
const RODAPE = `<footer class="footer"><div class="wrap cols">
<div><h4>Radar das Apreensões</h4><p>O conteúdo das reportagens pertence aos veículos de origem; cada notícia leva à fonte original.</p></div>
<div><h4>Navegue</h4><p><a href="/observatorio">Observatório</a> · <a href="/relatorios">Relatórios mensais</a></p><p><a href="/sobre">Sobre e expediente</a></p></div>
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
<meta name="theme-color" content="#ffffff"><link rel="icon" href="/img/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/source-serif-4.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="/assets/radar.css">
${jsonld ? `<script type="application/ld+json">${JSON.stringify(jsonld).replace(/</g, '\\u003c')}</script>` : ''}
<script type="module" src="/assets/pagina.js"></script><script defer src="/_vercel/insights/script.js"></script></head>
<body data-pagina="estatica">${cabecalho(atual)}<main id="conteudo" class="wrap" tabindex="-1">${corpo}</main>${RODAPE}</body></html>`;
}

// Texto completo (nota oficial ou licença aberta) como o órgão editou:
// "## " = intertítulo, "• " = item de lista, o resto são parágrafos.
function textoOriginalHTML(paragrafos) {
  let html = '', lista = [];
  const fechar = () => { if (lista.length) { html += `<ul class="tx-lista">${lista.join('')}</ul>`; lista = []; } };
  for (const p of paragrafos) {
    if (p.startsWith('• ')) { lista.push(`<li>${esc(p.slice(2))}</li>`); continue; }
    fechar();
    html += p.startsWith('## ') ? `<h3 class="tx-sub">${esc(p.slice(3))}</h3>` : `<p class="reader-text">${esc(p)}</p>`;
  }
  fechar();
  return html;
}

// Resumo do Radar: "O que aconteceu" em destaque; ação, envolvidos e órgãos em
// cartões; quem noticiou em etiquetas.
const ICONE_SECAO = {
  'Como foi a ação': '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
  'Envolvidos e próximos passos': '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  'Quem atuou': '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
};
function radarHTML(secoes, veiculos) {
  if (!secoes.length) return '';
  const icone = (t) => (ICONE_SECAO[t] ? `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONE_SECAO[t]}</svg>` : '');
  const lead = secoes.find(([t]) => t === 'O que aconteceu' || !t);
  const cartoes = secoes.filter(([t]) => ICONE_SECAO[t]);
  const importa = secoes.find(([t]) => t === 'Por que importa');
  const entenda = secoes.find(([t]) => t === 'Entenda');
  // "Skunk: variedade... Fuzil: arma..." -> pares termo/explicação.
  const termos = entenda ? entenda[1].split(/\s(?=[A-ZÀ-Ý][\wÀ-ÿ -]{1,40}: )/).map((x) => x.split(/: (.+)/s)).filter((x) => x[1]) : [];
  return `<section class="bloco radar"><header class="bloco-cab"><h2>Resumo do Radar</h2><p>Redigido pelo Radar a partir dos fatos publicados</p></header>` +
    (lead ? `<p class="rs-lead">${esc(lead[1])}</p>` : '') +
    (importa ? `<div class="rs-importa"><h3><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2l2.9 6.9L22 9.3l-5.4 4.8 1.6 7.2L12 17.6 5.8 21.3l1.6-7.2L2 9.3l7.1-.4z"/></svg>Por que importa</h3><p>${esc(importa[1])}</p></div>` : '') +
    (cartoes.length ? `<div class="rs-cards">${cartoes.map(([t, x]) => `<section class="rs-card"><h3>${icone(t)}${esc(t)}</h3><p>${esc(x)}</p></section>`).join('')}</div>` : '') +
    (termos.length ? `<div class="rs-entenda"><h3>Entenda</h3><dl>${termos.map(([t, x]) => `<div><dt>${esc(t)}</dt><dd>${esc(x)}</dd></div>`).join('')}</dl></div>` : '') +
    (veiculos.length > 1 ? `<div class="rs-veiculos"><h3>Quem noticiou</h3><ul>${veiculos.map((v) => `<li>${esc(v)}</li>`).join('')}</ul></div>` : '') +
    '</section>';
}

function kicker(n, cats) {
  const c = (n.c || [])[0];
  return `<div class="kicker">${c != null ? `<a href="/categoria/${SLUG_CAT[c]}">${esc(cats[c])}</a>` : 'Em classificação'}` +
    `${n.cid && n.uf ? ` · <a class="uf" href="${urlCidade(n.uf, n.cid)}">${esc(n.cid)} (${n.uf})</a>`
      : n.uf ? ` · <a class="uf" href="/estado/${n.uf}">${esc(ESTADOS[n.uf])}</a>` : ''}</div>`;
}
function itemLista(n, cats) {
  const foto = urlOk(n.img);
  return `<li><a class="story" href="${urlNoticia(n)}"><div>${kicker({ ...n, c: n.c }, cats).replace(/<a [^>]*>|<\/a>/g, '')}` +
    `<h3 class="headline">${esc(n.t)}</h3><div class="meta">${esc(fmtData(data(n)))} · ${esc(n.f || '')}` +
    `${n.o && n.o.length ? ` · <span class="sources">+${n.o.length} ${n.o.length === 1 ? 'fonte' : 'fontes'}</span>` : ''}</div></div>` +
    `<div class="media" data-cat="${(n.c || [8])[0]}"><img src="${esc(foto || `/api/foto?i=${n.i}`)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-ph></div></a></li>`;
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
    ['Cocaína', '≈ ' + qtd(s.coc || 0, 'kg')], ['Maconha e skunk', '≈ ' + qtd((s.mac || 0) + (s.skh || 0), 'kg')],
    ['Armas de fogo', '≈ ' + num(s.arm || 0)], ['Munições', '≈ ' + num(s.mun || 0)],
    ['Veículos de imprensa', num(new Set(itens.flatMap((n) => [n.f, ...(n.o || []).map((o) => o[0])]).filter(Boolean)).size)]];
  return `<dl class="kpis kpis-4">${linhas.map(([k, v]) => `<div class="kpi"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;
}

// ---------- páginas ----------
// Notícia ainda sem trecho ou sem fotos da matéria: lê o original na hora (até 4,5 s).
async function completar(n, t) {
  const falta = !(Array.isArray(t.p) && t.p.length) && !t.tr;
  const poucasFotos = !(Array.isArray(t.g) && t.g.length > 1);
  if (!falta && !poucasFotos) return t;
  try {
    const { lerNoticia } = require('./_extrair.js');
    const r = await Promise.race([lerNoticia(n, (await links())[n.i]), new Promise((ok) => setTimeout(() => ok(null), 4500))]);
    if (!r) return t;
    const novo = { ...t };
    if (falta && r.p) Object.assign(novo, { p: r.p, l: r.l });
    else if (falta && r.tr) Object.assign(novo, { tr: r.tr, tt: r.tt });
    if (poucasFotos && Array.isArray(r.g) && r.g.length > (t.g || []).length) novo.g = r.g;
    if (r.u) novo._u = r.u;
    return novo;
  } catch { return t; }
}

function compartilharHTML(n) {
  const link = SITE + urlNoticia(n);
  const origem = (o) => `${link}?utm_source=${o}&utm_medium=compartilhamento`;  // medição (assets/medir.js)
  const wa = `https://wa.me/?text=${encodeURIComponent(`${n.t} — Radar das Apreensões\n${origem('whatsapp')}`)}`;
  return `<div class="share-bar" aria-label="Compartilhar"><a class="share-wa" href="${esc(wa)}" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.4.8 3.2.7a2.8 2.8 0 0 0 1.8-1.3 2.3 2.3 0 0 0 .2-1.3c-.1-.1-.3-.2-.5-.3z"/></svg>Enviar no WhatsApp</a>` +
    `<button type="button" class="share-btn" data-copiar="${esc(origem('link'))}">Copiar link</button>` +
    `<button type="button" class="share-btn" data-compartilhar="${esc(origem('celular'))}" data-titulo="${esc(n.t)}">Compartilhar</button></div>`;
}

async function paginaNoticia(i) {
  const { feed } = dados();
  const comp = await noticiaCompleta(i);
  if (!comp) return null;
  const { n } = comp;
  const cats = feed.categorias;
  const t = await completar(n, comp.t);
  const url = urlOk(n.u) || urlOk(t._u || '');
  const d = data(n);
  const fotos = (Array.isArray(t.g) && t.g.length ? t.g : [n.img]).map(urlOk).filter(Boolean);
  const f = t.f || {};
  const ficha = [
    ['Apreendido', (f.apreendido || []).join(', ')],
    ['Onde', [(f.cidades || []).join(', ') || ESTADOS[n.uf] || '', f.rodovia ? `rodovia ${f.rodovia}` : ''].filter(Boolean).join(' · ')],
    ['Quem atuou', (f.orgaos || []).join(', ')],
    ['Presos', (f.presos_iniciais && f.presos_iniciais.length ? f.presos_iniciais.join(', ') + (f.presos > f.presos_iniciais.length ? ` (${num(f.presos)} no total)` : '')
      : f.presos ? `${num(f.presos)} ${f.presos === 1 ? 'pessoa' : 'pessoas'}` : (f.presos_texto ? 'Sim, segundo a reportagem' : ''))],
    ['Como', (f.como || []).join(', ')],
    ['Onde estava', [(f.esconderijo || []).join(', '), f.veiculo || ''].filter(Boolean).join(' · ')],
    ['Crimes citados', (f.crimes || []).join(', ')],
    ['Mandados', f.mandados || ''], ['Operação', f.operacao || ''], ['Valores citados', f.valor || ''],
    ['Publicado em', fmtData(d, true)],
  ].filter(([, v]) => v);
  const secoes = Array.isArray(t.sx) && t.sx.length ? t.sx : (t.s ? String(t.s).split(/\n{2,}/).filter(Boolean).map((p) => ['', p]) : []);
  const radar = radarHTML(secoes, [n.f, ...(n.o || []).map((o) => o[0])].filter(Boolean));
  const botao = url ? `<a class="btn" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Ler a reportagem completa em ${esc(n.f)} ↗</a>` : '';
  const cab = (titulo) => `<header class="bloco-cab"><h2>${titulo}</h2><p><strong>${esc(n.f || '')}</strong> · ${esc(fmtData(d))}</p></header>`;
  let fonte = '';
  if (Array.isArray(t.p) && t.p.length) {
    fonte = `<section class="bloco fonte-card">${cab('Texto completo')}<div class="fonte-texto">${textoOriginalHTML(t.p)}</div>` +
      `<footer class="fonte-pe"><span>${t.l === 'oficial' ? `Comunicado oficial de ${esc(n.f)}, reproduzido na íntegra com crédito.`
        : `Reproduzido de ${esc(n.f)} sob a licença ${esc(t.l)}, que permite a reprodução com crédito.`}</span>${botao}</footer></section>`;
  } else {
    const trecho = t.tr && t.tr.length > (n.r || '').length ? t.tr : n.r;
    const pct = t.tr && t.tt ? Math.min(100, Math.max(1, Math.round((t.tr.length / t.tt) * 100))) : 0;
    if (trecho) {
      fonte = `<section class="bloco fonte-card">${cab('O que diz a fonte')}<blockquote class="reader-quote">${paragrafos(trecho)}</blockquote>` +
        `<footer class="fonte-pe"><span>${t.tr ? `Trecho da reportagem${pct ? `, cerca de ${pct}% do texto original` : ''}, reproduzido com crédito.` : 'Resumo publicado pelo veículo, reproduzido com crédito.'}</span>${botao}</footer></section>`;
    } else if (botao) {
      fonte = `<section class="bloco fonte-card">${cab('O que diz a fonte')}<footer class="fonte-pe"><span>O trecho da reportagem ainda está sendo preparado. O texto completo e as fotos estão no site de origem.</span>${botao}</footer></section>`;
    }
  }
  // Relacionadas: mesmo estado e tipo, mais próximas no tempo.
  const relacionadas = feed.noticias.filter((x) => x.i !== i && x.uf && x.uf === n.uf && (x.c || [])[0] === (n.c || [])[0])
    .sort((a, b) => Math.abs(data(a) - d) - Math.abs(data(b) - d)).slice(0, 6);
  const descricao = corta((t.s || n.r || n.t).split('\n')[0], 160);
  const corpo = `<article class="artigo">${kicker(n, cats)}<h1 class="art-titulo">${esc(n.t)}</h1>
<div class="meta">${esc(fmtData(d, true))} · ${esc(n.f || '')}${url ? ` · <a href="${esc(url)}" target="_blank" rel="noopener noreferrer">ver original ↗</a>` : ''}</div>
${compartilharHTML(n)}
${fotos.length ? `<div class="art-fotos">${fotos.map((src, k) => `<img src="${esc(src)}" alt="${k ? '' : esc(n.t)}" ${k ? 'loading="lazy"' : 'fetchpriority="high"'} decoding="async" referrerpolicy="no-referrer">`).join('')}</div>
${fotos.length > 1 ? `<p class="reader-note">${fotos.length} fotos · deslize para ver todas. Imagens: ${esc(n.f)}.</p>` : `<p class="reader-note">Imagem: ${esc(n.f)}.</p>`}` : ''}
${ficha.length ? `<section class="em-resumo" aria-label="Em resumo"><h2>Em resumo</h2><dl>${ficha.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></section>` : ''}
${radar}
${fonte}
${n.o && n.o.length ? `<p class="reader-note tambem">Também noticiado por: ${n.o.map(([fo, u]) => (urlOk(u) ? `<a href="${esc(urlOk(u))}" target="_blank" rel="noopener noreferrer">${esc(fo)}</a>` : esc(fo))).join(', ')}.</p>` : ''}
</article>
${relacionadas.length ? `<div class="section-head"><h2>Mais de ${esc(cats[(n.c || [8])[0]])} ${n.uf ? `${PREP[n.uf]} ${esc(ESTADOS[n.uf])}` : ''}</h2><a href="/estado/${n.uf}">Ver o estado →</a></div>${lista(relacionadas, cats)}` : ''}`;
  const jsonld = {
    '@context': 'https://schema.org', '@type': 'NewsArticle', headline: corta(n.t, 110), datePublished: d ? d.toISOString() : undefined,
    image: fotos.slice(0, 3), description: descricao, mainEntityOfPage: `${SITE}${urlNoticia(n)}`,
    isBasedOn: url || undefined, author: { '@type': 'Organization', name: n.f || 'Radar das Apreensões' },
    publisher: { '@type': 'Organization', name: 'Radar das Apreensões', logo: { '@type': 'ImageObject', url: `${SITE}/img/icone-512.png` } },
  };
  return { html: pagina({ titulo: `${corta(n.t, 90)} | Radar das Apreensões`, descricao, canonico: urlNoticia(n), imagem: fotos[0], atual: 'Notícias', corpo, jsonld, indexar: indexavel(n) }), canonico: urlNoticia(n) };
}

function paginaLista({ titulo, h1, intro, itens, canonico, atual, rodape = '', indexar = true }) {
  const { feed } = dados();
  const agora = Date.now();
  const r30 = itens.filter((n) => data(n) && agora - data(n) <= 30 * 864e5);
  const r365 = itens.filter((n) => data(n) && agora - data(n) <= 365 * 864e5);
  const recentes = [...itens].sort((a, b) => (b.d || '').localeCompare(a.d || '')).slice(0, 60);
  const corpo = `<header class="pg-head"><h1 class="art-titulo">${esc(h1)}</h1><p class="dek">${esc(intro)}</p></header>
<div class="duas"><section class="panel"><h3>Últimos 30 dias</h3>${kpis(r30)}</section><section class="panel"><h3>Últimos 12 meses</h3>${kpis(r365)}</section></div>
<p class="note">Valores estimados com base nas quantidades informadas pela imprensa. Apreensões sem peso divulgado não integram a soma. Dados de caráter informativo, sem valor de estatística oficial.</p>
<div class="section-head"><h2>Notícias mais recentes</h2><span class="count">${num(itens.length)} no acervo</span></div>${lista(recentes, feed.categorias)}${rodape}`;
  return pagina({ titulo: `${titulo} | Radar das Apreensões`, descricao: intro, canonico, atual, corpo, indexar });
}

function paginaEstado(uf) {
  const { feed } = dados();
  if (!ESTADOS[uf]) return null;
  const itens = feed.noticias.filter((n) => n.uf === uf);
  const nome = ESTADOS[uf];
  return { html: paginaLista({
    titulo: `Apreensões ${PREP[uf]} ${nome}`, h1: `Apreensões ${PREP[uf]} ${nome}`, canonico: `/estado/${uf}`, atual: 'Notícias', itens,
    intro: `Notícias de apreensões de drogas, armas, contrabando e outros bens ${PREP[uf]} ${nome}, reunidas de veículos de imprensa e órgãos públicos e atualizadas o dia todo.`,
    rodape: listaCidades(uf) + `<p class="more"><a class="btn ghost" href="/#uf=${uf}">Ver todas e filtrar</a> <a class="btn ghost" href="/observatorio#uf=${uf}">Abrir no Observatório</a></p>`,
  }), canonico: `/estado/${uf}` };
}

function listaCidades(uf) {
  const lista = cidades().filter(([u, , v]) => u === uf && v >= 2).slice(0, 60);
  if (!lista.length) return '';
  return `<div class="section-head"><h2>Cidades com mais notícias</h2></div><ul class="chips-cidades">` +
    lista.map(([u, c, v]) => `<li><a href="${urlCidade(u, c)}">${esc(c)} <span>${num(v)}</span></a></li>`).join('') + '</ul>';
}

function paginaCidade(uf, s) {
  const { feed } = dados();
  if (!ESTADOS[uf]) return null;
  const achada = cidades().find(([u, c]) => u === uf && slug(c) === s);
  if (!achada) return null;
  const nome = achada[1];
  const itens = feed.noticias.filter((n) => n.uf === uf && n.cid === nome);
  return { html: paginaLista({
    titulo: `Apreensões em ${nome} (${uf})`, h1: `Apreensões em ${nome} (${uf})`, canonico: urlCidade(uf, nome), atual: 'Notícias', itens,
    intro: `Notícias de apreensões de drogas, armas, contrabando e outros bens em ${nome}, ${ESTADOS[uf]}, reunidas de veículos de imprensa e órgãos públicos e atualizadas o dia todo. A cidade é identificada automaticamente pelo texto da notícia.`,
    rodape: `<p class="more"><a class="btn ghost" href="/estado/${uf}">Ver ${PREP[uf]} ${esc(ESTADOS[uf])}</a> <a class="btn ghost" href="/#q=${encodeURIComponent(nome)}">Buscar “${esc(nome)}”</a></p>`,
    indexar: itens.length >= 3,
  }), canonico: urlCidade(uf, nome) };
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
  const { feed, indice } = dados();
  if (indice && indice.meses) return Object.entries(indice.meses).filter(([ym]) => ym >= '2006').sort((a, b) => b[0].localeCompare(a[0]));
  const m = new Map();
  for (const n of feed.noticias) if (n.d && n.d >= '2006') m.set(n.d.slice(0, 7), (m.get(n.d.slice(0, 7)) || 0) + 1);
  return [...m].sort((a, b) => b[0].localeCompare(a[0]));
}
const nomeMes = (ym) => `${MESES[Number(ym.slice(5, 7)) - 1]} de ${ym.slice(0, 4)}`;
// Meta de cobertura por mês (mesma de metas_cobertura.py): a coleta diária começou em out/2026 e
// os meses anteriores estão sendo completados pela coleta retroativa.
const INICIO_COLETA = '2026-10';
const metaMes = (ym) => { const a = Number(ym.slice(0, 4)); return a >= 2026 ? 2500 : a >= 2020 ? 1500 : a >= 2015 ? 800 : 300; };
const emFormacao = (ym, v) => ym < INICIO_COLETA && v < metaMes(ym);
const AVISO_COBERTURA = '<p class="note">A coleta diária do Radar começou em outubro de 2026. Os meses anteriores estão sendo completados aos poucos pela coleta retroativa (arquivos dos veículos, buscas por período e fontes oficiais); meses marcados como <em>em formação</em> ainda não têm cobertura comparável. Compare meses diferentes com cautela.</p>';

function paginaRelatorios() {
  const lista = meses().filter(([, v]) => v >= 20);
  const anos = new Map();
  for (const [ym, v] of lista) { const a = ym.slice(0, 4); if (!anos.has(a)) anos.set(a, []); anos.get(a).push([ym, v]); }
  const corpo = `<header class="pg-head"><h1 class="art-titulo">Relatórios mensais</h1><p class="dek">Para cada mês: total de notícias, estados e tipos mais frequentes, quantidades citadas e as maiores apreensões noticiadas. Gerados automaticamente a partir do acervo, sem duplicatas.</p></header>
${AVISO_COBERTURA}
${[...anos].map(([a, ms]) => `<div class="section-head"><h2>${a}</h2></div><ul class="meses">${ms.map(([ym, v]) =>
    `<li><a href="/relatorio/${ym}"><strong>${esc(nomeMes(ym))}</strong><span>${num(v)} notícias${emFormacao(ym, v) ? ' · <em>em formação</em>' : ''}</span></a></li>`).join('')}</ul>`).join('')}`;
  return { html: pagina({ titulo: 'Relatórios mensais de apreensões | Radar das Apreensões', descricao: 'Relatórios mensais automáticos das apreensões noticiadas no Brasil: rankings por estado, tipos e maiores apreensões.', canonico: '/relatorios', atual: 'Relatórios', corpo }), canonico: '/relatorios' };
}

async function paginaRelatorio(ym) {
  const { feed, indice } = dados();
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(ym)) return null;
  // Mês anterior ao feed.json: junta o arquivo do ano (sem repetir as que estão nos dois).
  const doAno = indice && indice.recorte && ym < indice.recorte.slice(0, 7) + '~' ? await anoArquivo(ym.slice(0, 4)) : [];
  const vistos = new Set();
  const itens = [...doAno, ...feed.noticias].filter((n) => n.d && n.d.startsWith(ym) && !vistos.has(n.i) && vistos.add(n.i));
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
${emFormacao(ym, itens.length) ? AVISO_COBERTURA : ''}${kpis(itens)}<p class="note">Valores estimados com base nas quantidades informadas pela imprensa. Apreensões sem peso divulgado não integram a soma. Dados de caráter informativo, sem valor de estatística oficial.</p>
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
<p class="reader-text">A coleta é automática e roda o dia todo, a cada 20 minutos. Cada notícia passa por regras próprias que decidem se ela trata de uma apreensão e de qual tipo, identificam o estado, agrupam as versões da mesma notícia publicadas por veículos diferentes e extraem os fatos principais (o que foi apreendido, quanto, onde, quem atuou).</p>
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
<h2>3. Conteúdo do Radar</h2><p class="reader-text">Os resumos, fichas e indicadores redigidos pelo Radar podem ser citados, desde que indicada a fonte: "Radar das Apreensões".</p>
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

module.exports = async (req, res) => {
  const u = new URL(req.url, SITE);
  const tipo = u.searchParams.get('tipo');
  const id = u.searchParams.get('id') || '';
  let r = null;
  try {
    await carregar(req);
    if (tipo === 'noticia') r = await paginaNoticia(Number((id.match(/^\d+/) || [''])[0]));
    else if (tipo === 'estado') r = paginaEstado(id.toUpperCase());
    else if (tipo === 'cidade') r = paginaCidade(id.toUpperCase(), (u.searchParams.get('cidade') || '').toLowerCase());
    else if (tipo === 'categoria') r = paginaCategoria(id.toLowerCase());
    else if (tipo === 'relatorios') r = paginaRelatorios();
    else if (tipo === 'relatorio') r = await paginaRelatorio(id);
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
module.exports.links = links;
module.exports.carregar = carregar;
module.exports.noticiaCompleta = noticiaCompleta;
module.exports.urlNoticia = urlNoticia;
module.exports.indexavel = indexavel;
module.exports.meses = meses;
module.exports.SLUG_CAT = SLUG_CAT;
module.exports.ESTADOS = ESTADOS;
module.exports.cidades = cidades;
module.exports.urlCidade = urlCidade;
