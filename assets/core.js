/* Radar das Apreensões — núcleo compartilhado (dados, utilidades, mapa e gráficos). */
export const $ = (id) => document.getElementById(id);
export const ESTADOS = [
  ['AC', 'Acre'], ['AL', 'Alagoas'], ['AP', 'Amapá'], ['AM', 'Amazonas'], ['BA', 'Bahia'], ['CE', 'Ceará'],
  ['DF', 'Distrito Federal'], ['ES', 'Espírito Santo'], ['GO', 'Goiás'], ['MA', 'Maranhão'], ['MT', 'Mato Grosso'],
  ['MS', 'Mato Grosso do Sul'], ['MG', 'Minas Gerais'], ['PA', 'Pará'], ['PB', 'Paraíba'], ['PR', 'Paraná'],
  ['PE', 'Pernambuco'], ['PI', 'Piauí'], ['RJ', 'Rio de Janeiro'], ['RN', 'Rio Grande do Norte'],
  ['RS', 'Rio Grande do Sul'], ['RO', 'Rondônia'], ['RR', 'Roraima'], ['SC', 'Santa Catarina'], ['SP', 'São Paulo'],
  ['SE', 'Sergipe'], ['TO', 'Tocantins'],
];
export const NOME_UF = Object.fromEntries(ESTADOS);
export const CURTO = ['Drogas', 'Armas', 'Contrabando', 'Veículos', 'Dinheiro', 'Ambientais', 'Medicamentos', 'Patrimoniais', 'Outras'];

// ---------- utilidades ----------
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const fold = (v) => String(v ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
export const urlSegura = (v) => { try { const u = new URL(v); return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : ''; } catch { return ''; } };
export const num = (n, d = 0) => Number(n).toLocaleString('pt-BR', { maximumFractionDigits: d });
export const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const dataBR = (d) => d ? d.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo', day: 'numeric', month: 'short', year: 'numeric' }).replace(/\./g, '') : 'Data não informada';
export const horaBR = (d) => d ? d.toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit' }) : '';
export function relativo(d) {
  if (!d) return '';
  const min = Math.round((Date.now() - d.getTime()) / 60000);
  if (min < 60) return `há ${Math.max(1, min)} min`;
  if (min < 24 * 60) return `há ${Math.round(min / 60)} h`;
  return dataBR(d);
}
/** Quantidade com unidade legível: 1.250 kg -> "1,3 t"; 15000 un -> "15 mil". */
export function qtd(valor, unidade) {
  if (unidade === 'kg') return valor >= 1000 ? `${num(valor / 1000, 1)} t` : `${num(valor, valor < 10 ? 1 : 0)} kg`;
  if (valor >= 1e6) return `${num(valor / 1e6, 1)} mi`;
  if (valor >= 1e4) return `${num(valor / 1e3, 0)} mil`;
  return num(valor);
}

/** Endereço da página própria da notícia (o mesmo slug de api/pagina.js). */
export const slug = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').split('-').slice(0, 12).join('-');
export const urlNoticia = (n) => `/noticia/${n.i}-${slug(n.titulo ?? n.t)}`;

// ---------- ícones das editorias (traço simples, sem texto embutido) ----------
const I = (d) => `<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
export const ICONES = [
  I('<path d="M24 6c3 8 3 14 0 20M24 26c-6-2-11-7-13-14 7 1 11 5 13 14zM24 26c6-2 11-7 13-14-7 1-11 5-13 14zM24 26v16"/>'),
  I('<path d="M6 18h30l4 4v6H26l-4 8h-8l3-8H6z"/><path d="M14 18v-4h8v4"/>'),
  I('<rect x="6" y="14" width="22" height="20" rx="2"/><path d="M28 20h8l6 7v7H28zM6 22h22"/><circle cx="14" cy="36" r="3"/><circle cx="34" cy="36" r="3"/>'),
  I('<path d="M8 30l4-10h24l4 10v6H8z"/><circle cx="15" cy="36" r="3"/><circle cx="33" cy="36" r="3"/><path d="M14 20l3-6h14l3 6"/>'),
  I('<rect x="6" y="14" width="36" height="20" rx="2"/><circle cx="24" cy="24" r="5"/><path d="M11 19h2M35 29h2"/>'),
  I('<path d="M24 42V24M24 24c-8 0-12-6-12-12 6 0 12 4 12 12zM24 30c6 0 12-4 12-12-6 0-12 4-12 12z"/>'),
  I('<rect x="10" y="18" width="28" height="12" rx="6" transform="rotate(-35 24 24)"/><path d="M20 14l8 20"/>'),
  I('<path d="M8 40h32M10 36h28M12 20h24v16H12zM8 20l16-12 16 12"/><path d="M18 24v8M24 24v8M30 24v8"/>'),
  I('<circle cx="20" cy="20" r="11"/><path d="M28 28l12 12"/>'),
];
export function placeholder(n) {
  const c = n.cats[0] ?? 8;
  return `<div class="ph" role="img" aria-label="Sem foto: ${esc(CURTO[c])}">${ICONES[c]}<span>${esc(CURTO[c])}</span></div>`;
}
export const imgTag = (src, alt = '', extra = '') =>
  `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" ${extra}>`;
export function midia(n, { contador = false } = {}) {
  const foto = n.img ? imgTag(n.img, '', 'data-ph') : placeholder(n);
  const extra = contador && n.nFotos > 1 ? `<span class="count">${n.nFotos} fotos</span>` : '';
  return `<div class="media" data-cat="${n.cats[0] ?? 8}">${foto}${extra}</div>`;
}
// Foto externa que falha vira o marcador da editoria.
document.addEventListener('error', (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement) || !img.hasAttribute('data-ph')) return;
  const box = img.closest('.media');
  const c = Number(box?.dataset.cat ?? 8);
  img.outerHTML = `<div class="ph">${ICONES[c]}<span>${esc(CURTO[c])}</span></div>`;
}, true);

// ---------- dados ----------
function preparar(raw, ctx) {
  const d = raw.d ? new Date(raw.d.length === 16 ? raw.d + 'Z' : raw.d) : null;
  const data = d && Number.isFinite(d.getTime()) ? d : null;
  const cats = (raw.c || []).filter((c) => ctx.categorias[c]);
  const uf = NOME_UF[raw.uf] ? raw.uf : '';
  const n = {
    i: raw.i, titulo: raw.t, fonte: raw.f || 'Fonte não informada', resumo: raw.r || '',
    url: urlSegura(raw.u || ''), img: urlSegura(raw.img || ''), uf, cats, data,
    texto: raw.x === 1, nFotos: raw.g || (raw.img ? 1 : 0),
    outras: Array.isArray(raw.o) ? raw.o.filter((o) => Array.isArray(o) && o[0]) : [],
    q: raw.q || null, ag: raw.ag || [], rd: raw.rd || '', vq: raw.vq || 0, cidade: uf ? raw.cid || '' : '',
    ano: data ? data.getUTCFullYear() : null,
  };
  // Texto de busca em palavras separadas por espaço (" foz do iguacu "): a busca casa
  // pelo começo da palavra, nunca no meio ("#fozdoiguacu" não vale como "iguacu").
  // Cidades de trajeto ("seguia para Curitiba") não contam na busca: só o local da apreensão.
  const semTrajeto = (t) => (Array.isArray(raw.rt) ? raw.rt : []).reduce((acc, c) => acc.split(c).join(' '), t || '');
  n.busca = ' ' + fold([semTrajeto(n.titulo), semTrajeto(n.resumo), n.fonte, n.cidade, uf, NOME_UF[uf], cats.map((c) => ctx.categorias[c]).join(' '),
    n.ag.map((a) => ctx.orgaos[a]).join(' '), n.rd].join(' ')).replace(/[^a-z0-9]+/g, ' ') + ' ';
  return n;
}

// Segunda barreira contra duplicidade: mesma regra de gerar_feed_site.py.
const VAZIAS = new Set('para pela pelo pelos pelas com sem sobre apos entre durante contra como mais menos que uma umas uns dos das nos nas aos este esta esse essa isso isto pode podem diz afirma'.split(' '));
const GENERICAS = new Set('policia policias policial policiais militar militares civil federal rodoviaria apreende apreendem apreendeu apreendido apreendida apreendidos apreendidas apreensao apreensoes prende prendem prendeu preso presa presos presas prisao flagrante suspeito suspeitos suspeita homem mulher jovem jovens adolescente pessoas dupla trio operacao acao durante cerca mais droga drogas trafico traficante bairro cidade regiao estado'.split(' '));
const EXTENSO = { um: '1', uma: '1', dois: '2', duas: '2', tres: '3', quatro: '4', cinco: '5', seis: '6', sete: '7', oito: '8', nove: '9', dez: '10', onze: '11', doze: '12', treze: '13', quatorze: '14', catorze: '14', quinze: '15', vinte: '20', trinta: '30', cem: '100' };
const ANOS = new Set(['2024', '2025', '2026']);
const tokens = (t) => fold(t).replace(/[^a-z0-9]+/g, ' ').trim().split(' ').filter(Boolean);
function assinatura(n) {
  const pal = new Set(), inf = new Set(), qt = new Set();
  for (const w of tokens(n.titulo)) {
    if (/^\d+$/.test(w)) { if (!ANOS.has(w)) { qt.add(w.replace(/^0+(?=\d)/, '')); if (w.length >= 2) inf.add(w); } continue; }
    if (EXTENSO[w]) qt.add(EXTENSO[w]);
    if (w.length > 3 && !VAZIAS.has(w)) { pal.add(w); if (!GENERICAS.has(w)) inf.add(w); }
  }
  return { pal, inf, qt, norm: tokens(n.titulo).join(' ') };
}
const comuns = (a, b) => { let c = 0; for (const x of a) if (b.has(x)) c++; return c; };
function mesmaMateria(a, b, mesmoUf) {
  if (a.qt.size && b.qt.size && !comuns(a.qt, b.qt)) return false;
  const c = comuns(a.pal, b.pal);
  if (c >= 4 && c / (a.pal.size + b.pal.size - c) >= 0.65) return true;
  const inf = comuns(a.inf, b.inf);
  const numero = comuns(a.qt, b.qt) > 0 || [...a.inf].some((w) => /^\d+$/.test(w) && b.inf.has(w));
  return inf >= 3 && inf / Math.max(1, Math.min(a.inf.size, b.inf.size)) >= 0.75 && (mesmoUf || numero) && (inf >= 4 || numero);
}
const pontos = (n) => (n.texto ? 8 : 0) + Math.min(n.nFotos || 0, 5) * 2 + (n.url ? 3 : 0) + (n.uf ? 1 : 0) + (n.resumo ? 1 : 0);
function deduplicar(lista) {
  const pai = lista.map((_, k) => k);
  const raiz = (k) => { while (pai[k] !== k) { pai[k] = pai[pai[k]]; k = pai[k]; } return k; };
  const unir = (a, b) => { pai[raiz(b)] = raiz(a); };
  const sig = lista.map(assinatura);
  const porTitulo = new Map(), porDia = new Map();
  lista.forEach((n, k) => {
    if (sig[k].norm.length > 25) { if (porTitulo.has(sig[k].norm)) unir(porTitulo.get(sig[k].norm), k); else porTitulo.set(sig[k].norm, k); }
    const dia = n.data ? n.data.toISOString().slice(0, 10) : '';
    if (dia) { if (!porDia.has(dia)) porDia.set(dia, []); porDia.get(dia).push(k); }
  });
  const dias = [...porDia.keys()].sort();
  dias.forEach((dia, p) => {
    const atuais = porDia.get(dia), viz = atuais.concat(p + 1 < dias.length ? porDia.get(dias[p + 1]) : []);
    atuais.forEach((a, ia) => {
      if (sig[a].pal.size < 3) return;
      for (let j = ia + 1; j < viz.length; j++) {
        const b = viz[j], ua = lista[a].uf, ub = lista[b].uf;
        if (ua && ub && ua !== ub) continue;
        if (mesmaMateria(sig[a], sig[b], !!(ua && ua === ub))) unir(a, b);
      }
    });
  });
  const grupos = new Map();
  lista.forEach((_, k) => { const r = raiz(k); if (!grupos.has(r)) grupos.set(r, []); grupos.get(r).push(k); });
  const saida = [];
  for (const membros of grupos.values()) {
    membros.sort((x, y) => pontos(lista[y]) - pontos(lista[x]));
    const p = lista[membros[0]];
    const vistas = new Set([p.fonte, ...p.outras.map((o) => o[0])]);
    for (const k of membros.slice(1)) {
      const o = lista[k];
      if (!p.img && o.img) p.img = o.img;
      if (!p.uf && o.uf) p.uf = o.uf;
      if (!p.resumo && o.resumo) p.resumo = o.resumo;
      if (!p.q && o.q) p.q = o.q;
      p.cats = [...new Set([...p.cats, ...o.cats])];
      for (const [fonte, url, i] of [[o.fonte, o.url, o.i], ...o.outras]) if (!vistas.has(fonte)) { vistas.add(fonte); p.outras.push([fonte, url, i]); }
    }
    saida.push(p);
  }
  return saida;
}

/** Carrega e prepara o acervo (uma vez por página). */
const feeds = new Map();
/** feed.json (completo) ou feed-recente.json (últimos 31 dias, para a página inicial abrir rápido). */
export function carregarFeed(arquivo = 'feed.json') {
  if (feeds.has(arquivo)) return feeds.get(arquivo);
  const feedPromise = fetch(arquivo).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then((dados) => {
    const ctx = {
      categorias: dados.categorias || [], orgaos: dados.orgaos || [], materiais: dados.materiais || {},
      atualizado: dados.atualizado_em ? new Date(dados.atualizado_em) : null,
    };
    ctx.noticias = deduplicar((dados.noticias || []).map((n) => preparar(n, ctx)))
      .sort((a, b) => (b.data?.getTime() || 0) - (a.data?.getTime() || 0));
    ctx.porIndice = new Map(ctx.noticias.map((n) => [n.i, n]));
    ctx.parcial = Boolean(dados.parcial);
    return ctx;
  });
  feeds.set(arquivo, feedPromise);
  return feedPromise;
}

// ---------- cabeçalho comum ----------
export function iniciarCabecalho(ctxPromise) {
  const hoje = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Sao_Paulo' });
  if ($('hoje')) $('hoje').textContent = hoje.charAt(0).toUpperCase() + hoje.slice(1);
  ctxPromise.then((ctx) => {
    if ($('atualizado') && ctx.atualizado) $('atualizado').textContent = `Atualizado ${relativo(ctx.atualizado)} · ${num(ctx.noticias.length)} notícias`;
  }).catch(() => {});
  const form = $('formBusca');
  form?.addEventListener('submit', (e) => {
    const q = $('buscaTopo').value.trim();
    if (document.body.dataset.pagina === 'central') return; // a Central trata a busca no próprio lugar
    e.preventDefault();
    location.href = './' + (q ? '#q=' + encodeURIComponent(q) : '');
  });
  // Tema: claro por padrão; a escolha do leitor fica salva neste navegador.
  const raiz = document.documentElement;
  try { const t = localStorage.getItem('tema'); if (t) raiz.dataset.theme = t; } catch { /* armazenamento indisponível */ }
  $('tema')?.addEventListener('click', () => {
    const escuro = (raiz.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark';
    raiz.dataset.theme = escuro ? 'light' : 'dark';
    try { localStorage.setItem('tema', raiz.dataset.theme); } catch { /* ignore */ }
  });
}

// ---------- dica flutuante ----------
let tipEl = null;
export function dica(html, ev) {
  tipEl ??= Object.assign(document.body.appendChild(document.createElement('div')), { className: 'tip', role: 'tooltip' });
  if (!html) { tipEl.hidden = true; return; }
  tipEl.hidden = false;
  tipEl.innerHTML = html;
  const x = Math.min(ev.clientX + 14, innerWidth - tipEl.offsetWidth - 8);
  const y = ev.clientY + 16 + tipEl.offsetHeight > innerHeight ? ev.clientY - tipEl.offsetHeight - 10 : ev.clientY + 16;
  tipEl.style.left = x + 'px';
  tipEl.style.top = y + 'px';
}

// ---------- mapa do Brasil (coroplético, uma cor) ----------
let mapaPromise = null;
const carregarMapa = () => (mapaPromise ??= fetch('assets/mapa-brasil.json').then((r) => r.json()));
/**
 * valores: {UF: número}. Classes por quantis (5 tons de azul); zero em cinza.
 * opts: { sel, aoClicar(uf), formato(v), rotulo }
 */
export async function renderMapa(el, valores, opts = {}) {
  const mapa = await carregarMapa();
  const vs = Object.values(valores).filter((v) => v > 0).sort((a, b) => a - b);
  const cortes = [0.2, 0.4, 0.6, 0.8].map((p) => vs[Math.floor(p * (vs.length - 1))] ?? 0);
  const classe = (v) => (v > 0 ? 1 + cortes.filter((c) => v > c).length : 0);
  const fmt = opts.formato || ((v) => num(v));
  el.innerHTML = `<svg viewBox="${mapa.viewBox}" role="group" aria-label="${esc(opts.rotulo || 'Mapa do Brasil')}">` +
    Object.entries(mapa.estados).map(([uf, d]) => {
      const v = valores[uf] || 0, c = classe(v);
      return `<path d="${d}" data-uf="${uf}" tabindex="0" role="button" class="${opts.sel === uf ? 'sel' : ''}" ` +
        `style="fill:var(${c ? '--seq-' + c : '--zero'})" aria-label="${esc(NOME_UF[uf])}: ${esc(fmt(v))}"></path>`;
    }).join('') + '</svg>' +
    `<div class="legend" aria-hidden="true"><span>menos</span>${[1, 2, 3, 4, 5].map((c) => `<i style="background:var(--seq-${c})"></i>`).join('')}<span>mais</span>` +
    `<i style="background:var(--zero);margin-left:10px"></i><span>sem registro</span></div>`;
  const svg = el.querySelector('svg');
  svg.addEventListener('mousemove', (e) => {
    const p = e.target.closest('path');
    dica(p ? `<b>${esc(NOME_UF[p.dataset.uf])}</b><br>${esc(fmt(valores[p.dataset.uf] || 0))}` : '', e);
  });
  svg.addEventListener('mouseleave', () => dica(''));
  const acionar = (p) => p && opts.aoClicar?.(p.dataset.uf);
  svg.addEventListener('click', (e) => acionar(e.target.closest('path')));
  svg.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); acionar(e.target.closest('path')); } });
}

// ---------- ranking em barras (série única) ----------
export function ranking(el, linhas, { attr = '', sel = '', formato = (v) => num(v), max = 10 } = {}) {
  const top = linhas.filter(([, v]) => v > 0).slice(0, max);
  const maior = Math.max(1, ...top.map(([, v]) => v));
  el.innerHTML = top.length ? top.map(([chave, v, rotulo]) =>
    `<button type="button" ${attr ? `${attr}="${esc(chave)}"` : ''} aria-pressed="${sel === chave}"><span>${esc(rotulo ?? chave)}</span>` +
    `<span class="v">${esc(formato(v))}</span><span class="bar"><span style="width:${Math.max(1.5, (100 * v) / maior).toFixed(1)}%"></span></span></button>`).join('')
    : '<p class="note">Sem dados para este recorte.</p>';
}

// ---------- série mensal em colunas ----------
export function serie(el, pontos, { formato = (v) => num(v), rotulo = '' } = {}) {
  const W = 900, H = 240, m = { t: 12, r: 8, b: 26, l: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const maior = Math.max(1, ...pontos.map((p) => p.v));
  const passo = Math.pow(10, Math.floor(Math.log10(maior)));
  const topo = Math.ceil(maior / passo) * passo;
  const bw = iw / Math.max(1, pontos.length), gap = Math.min(4, bw * 0.25);
  const ticks = [0, 0.5, 1].map((f) => topo * f);
  const cada = Math.ceil(pontos.length / 12);
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(rotulo)}">` +
    ticks.map((t) => { const y = m.t + ih - (t / topo) * ih; return `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${y}" y2="${y}"/><text class="axis" x="${m.l - 6}" y="${y + 4}" text-anchor="end">${esc(formato(t))}</text>`; }).join('') +
    pontos.map((p, k) => {
      const h = (p.v / topo) * ih, x = m.l + k * bw + gap / 2, y = m.t + ih - h, w = Math.max(1, bw - gap);
      const r = Math.min(4, w / 2, h);
      const barra = h > 0 ? `<path class="col" d="M${x},${m.t + ih} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${m.t + ih} Z"/>` : '';
      const lab = k % cada === 0 ? `<text class="axis" x="${x + w / 2}" y="${H - 8}" text-anchor="middle">${esc(p.curto)}</text>` : '';
      return `${barra}${lab}<rect class="hit" data-k="${k}" x="${m.l + k * bw}" y="${m.t}" width="${bw}" height="${ih}"/>`;
    }).join('') + '</svg>';
  const svg = el.querySelector('svg');
  svg.addEventListener('mousemove', (e) => {
    const r = e.target.closest('.hit');
    svg.querySelectorAll('.col').forEach((c) => c.classList.remove('hi'));
    if (!r) return dica('', e);
    const p = pontos[Number(r.dataset.k)];
    const col = svg.querySelectorAll('.col')[pontos.slice(0, Number(r.dataset.k)).filter((q) => q.v > 0).length];
    if (p.v > 0 && col) col.classList.add('hi');
    dica(`<b>${esc(p.longo)}</b><br>${esc(formato(p.v))}`, e);
  });
  svg.addEventListener('mouseleave', () => { dica(''); svg.querySelectorAll('.col').forEach((c) => c.classList.remove('hi')); });
}
