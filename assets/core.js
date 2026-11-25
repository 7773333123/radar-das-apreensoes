import { BRASOES } from './brasoes.js';
import './medir.js';
/* Radar das Apreensões — núcleo compartilhado (dados, utilidades, mapa e gráficos). */
export const $ = (id) => document.getElementById(id);
// Dados do site (notícias, anos, textos) no GitHub Pages, gratuito (custo da Vercel, 25/11/2026): a Vercel
// publica só quando o código muda. Se o Pages falhar, usa a cópia publicada pelo próprio site.
export const DADOS = 'https://7773333123.github.io/radar-das-apreensoes/';
export function buscarDados(caminho, opcoes) {
  const c = String(caminho).replace(/^\//, '');
  return fetch(DADOS + c, opcoes)
    .then((r) => (r.ok ? r : Promise.reject(new Error('HTTP ' + r.status))))
    .catch(() => fetch('/' + c, opcoes));
}
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
// Ícones cheios (24/11/2026): folha de maconha e pistola, mais fáceis de reconhecer que o traço.
const F = (d) => `<svg viewBox="0 0 48 48" fill="currentColor" stroke="none" aria-hidden="true">${d}</svg>`;
// Outros ícones dos painéis: tablete de droga (cocaína), munição, mapa e jornal.
// Conjunto cheio e moderno (24/11/2026), o mesmo estilo em todo o site.
export const ICONE = {
  tablete: F('<path d="M24 6l19 8.5-19 8.5L5 14.5z"/><path d="M5 18l17 7.6V43L5 35.4z" opacity=".75"/><path d="M43 18l-17 7.6V43l17-7.6z" opacity=".9"/>'),
  municao: F('<path d="M9 25c0-8 5.5-17 5.5-17S20 17 20 25z"/><path d="M9 28h11v15H9z"/><path d="M28 25c0-8 5.5-17 5.5-17S39 17 39 25z"/><path d="M28 28h11v15H28z"/>'),
  mapa: F('<path fill-rule="evenodd" d="M24 45S9.5 32.5 9.5 21a14.5 14.5 0 0 1 29 0C38.5 32.5 24 45 24 45zm0-18.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11z"/>'),
  jornal: F('<path fill-rule="evenodd" d="M8 7h27v34H13a5 5 0 0 1-5-5zM14 14v3.5h15V14zM14 21.5V25h15v-3.5zM14 29v3.5h9V29z"/><path d="M37 15h5v21a5 5 0 0 1-5 5z"/>'),
  relogio: F('<path fill-rule="evenodd" d="M24 5a19 19 0 1 0 0 38 19 19 0 0 0 0-38zm-1.8 8h3.6v10.2l7.3 4.2-1.8 3.1-9.1-5.3z"/>'),
  sirene: F('<path d="M12 36V25.5a12 12 0 0 1 24 0V36z"/><path d="M7 38.5h34V44H7z"/><path d="M22.4 3h3.2v7h-3.2zM7.3 9.6l2.3-2.3 5 5-2.3 2.3zM40.7 9.6l-2.3-2.3-5 5 2.3 2.3z"/>'),
  grafico: F('<path d="M6 25h7v14H6zM16.5 15h7v24h-7zM27 20h7v19h-7zM37.5 8h7v31h-7z"/><path d="M4 41.5h42V45H4z"/>'),
};
export const ICONES = [
  F('<path transform="rotate(0 24 31)" d="M24 31C18.1 18.9 19.7 8.1 24 4C28.3 8.1 29.9 18.9 24 31Z"/><path transform="rotate(-38 24 31)" d="M24 31C18.9 20.6 20.3 11.4 24 8C27.7 11.4 29.1 20.6 24 31Z"/><path transform="rotate(38 24 31)" d="M24 31C18.9 20.6 20.3 11.4 24 8C27.7 11.4 29.1 20.6 24 31Z"/><path transform="rotate(-78 24 31)" d="M24 31C20.3 23.4 21.3 16.6 24 14C26.7 16.6 27.7 23.4 24 31Z"/><path transform="rotate(78 24 31)" d="M24 31C20.3 23.4 21.3 16.6 24 14C26.7 16.6 27.7 23.4 24 31Z"/><path transform="rotate(-112 24 31)" d="M24 31C21.8 26.5 22.4 22.5 24 21C25.6 22.5 26.2 26.5 24 31Z"/><path transform="rotate(112 24 31)" d="M24 31C21.8 26.5 22.4 22.5 24 21C25.6 22.5 26.2 26.5 24 31Z"/><rect x="22.8" y="31" width="2.4" height="13" rx="1.2"/>'),
  F('<path d="M5 13h35a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H25.5l-1.2 2.6a4 4 0 0 1-3.6 2.4H19l-2.6 11.4a2 2 0 0 1-2 1.6H8.6a1.5 1.5 0 0 1-1.5-1.8L10 23H5a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2Z"/><path d="M38 11h3v2h-3z"/>'),
  F('<path d="M3 11h25a1 1 0 0 1 1 1v20H3a1 1 0 0 1-1-1V12a1 1 0 0 1 1-1z"/><path d="M31 17h7.5a2 2 0 0 1 1.6.8l5.4 7.2V32H31z"/><circle cx="11" cy="36" r="4.5"/><circle cx="37" cy="36" r="4.5"/>'),
  F('<path fill-rule="evenodd" d="M6 26l4.6-9.6A4 4 0 0 1 14.2 14h19.6a4 4 0 0 1 3.6 2.4L42 26v8a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2zM13.5 25h21l-3-7.5h-15z"/><circle cx="14" cy="37" r="4.5"/><circle cx="34" cy="37" r="4.5"/>'),
  F('<path d="M8 9h34a2 2 0 0 1 2 2v1H10a2 2 0 0 0-2 2z" opacity=".6"/><path fill-rule="evenodd" d="M6 15h36a2 2 0 0 1 2 2v18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V17a2 2 0 0 1 2-2zM24 20a6 6 0 1 0 0 12 6 6 0 0 0 0-12z"/>'),
  F('<path d="M41 6C20 6 8 16 8 31c0 3 .6 5.8 1.6 8.2L5.5 43.3l2.2 2.2 4-4C14.2 42.5 17 43 20 43c15 0 21-15 21-37z"/>'),
  F('<g transform="rotate(-40 24 24)"><path d="M11 17h12v14H11a7 7 0 0 1 0-14z"/><path d="M25 17h12a7 7 0 0 1 0 14H25z" opacity=".6"/></g>'),
  F('<path d="M24 4L4 14.5V19h40v-4.5z"/><path d="M8 21h5v15H8zM17 21h5v15h-5zM26 21h5v15h-5zM35 21h5v15h-5z"/><path d="M4 38h40v6H4z"/>'),
  F('<path fill-rule="evenodd" d="M20 5a15 15 0 1 0 8.9 27.1l9.4 9.4 3.2-3.2-9.4-9.4A15 15 0 0 0 20 5zm0 5a10 10 0 1 1 0 20 10 10 0 0 1 0-20z"/>'),
];
// Sem foto: o brasão oficial da instituição que fez a ação (img/brasoes, conferidos à mão) e o
// nome dela; sem brasão disponível, um escudo genérico; sem órgão identificado, a editoria.
const CHAVE_BRASAO = { 'Polícia Rodoviária Federal': 'prf', 'Polícia Federal': 'pf', 'Receita Federal': 'receita',
  'Força Nacional': 'forca-nacional', 'Marinha': 'marinha', 'Exército': 'exercito', 'Polícia Militar': 'pm-', 'Polícia Civil': 'pc-' };
function brasao(orgao, uf) {
  let k = CHAVE_BRASAO[orgao];
  if (!k) return '';
  if (k.endsWith('-')) k = uf ? k + uf.toLowerCase() : '';
  return k && BRASOES.has(k) ? `<img class="brasao" src="/img/brasoes/${k}.png" alt="" loading="lazy" decoding="async">` : '';
}
const ESCUDO = I('<path d="M24 5l15 5v11c0 10-6.5 17.5-15 22-8.5-4.5-15-12-15-22V10z"/><path d="M17 24l5 5 9-10"/>');
function marcador(c, orgao, uf = '') {
  return orgao
    ? `<div class="ph ph-org" role="img" aria-label="Sem foto: ${esc(orgao)}">${brasao(orgao, uf) || ESCUDO}<span>${esc(orgao)}</span></div>`
    : `<div class="ph" role="img" aria-label="Sem foto: ${esc(CURTO[c])}">${ICONES[c]}<span>${esc(CURTO[c])}</span></div>`;
}
export function placeholder(n) {
  return marcador(n.cats[0] ?? 8, n.orgao, n.uf);
}
export const imgTag = (src, alt = '', extra = '') =>
  `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" ${extra}>`;
export function midia(n, { contador = false } = {}) {
  // Sem foto ainda: o servidor busca a foto da matéria original (cache de 7 dias); se não houver, vira o marcador.
  // Só havia foto com marca d'água/nome do jornal (sf): marcador da editoria, sem buscar a original.
  if (!n.img && n.semFoto) return `<div class="media" data-cat="${n.cats[0] ?? 8}">${placeholder(n)}</div>`;
  const foto = n.img ? imgTag(n.img, '', 'data-ph') : imgTag(`/api/foto?i=${n.i}`, '', 'data-ph');
  const extra = (n.video ? '<span class="vid">▶ Vídeo</span>' : '') + (contador && n.nFotos > 1 ? `<span class="count">${n.nFotos} fotos</span>` : '');
  return `<div class="media" data-cat="${n.cats[0] ?? 8}"${n.orgao ? ` data-org="${esc(n.orgao)}" data-uf="${esc(n.uf || '')}"` : ''}>${foto}${extra}</div>`;
}
// Foto externa que falha vira o marcador da editoria.
document.addEventListener('error', (e) => {
  const img = e.target;
  if (!(img instanceof HTMLImageElement) || !img.hasAttribute('data-ph')) return;
  const box = img.closest('.media');
  const c = Number(box?.dataset.cat ?? 8);
  img.outerHTML = marcador(c, box?.dataset.org || '', box?.dataset.uf || '');
}, true);

// ---------- dados ----------
function preparar(raw, ctx) {
  const d = raw.d ? new Date(raw.d.length === 16 ? raw.d + 'Z' : raw.d) : null;
  const data = d && Number.isFinite(d.getTime()) ? d : null;
  const cats = (raw.c || []).filter((c) => ctx.categorias[c]);
  const uf = NOME_UF[raw.uf] ? raw.uf : '';
  const n = {
    i: raw.i, titulo: raw.t, fonte: raw.f || 'Fonte não informada', resumo: raw.r || '',
    url: urlSegura(raw.u || ''), temLink: Boolean(raw.u || raw.uh), img: urlSegura(raw.img || ''), uf, cats, data,
    texto: raw.x === 1, semFoto: raw.sf === 1, fotoMaterial: raw.pm === 1, video: raw.vd === 1, creditoFoto: raw.fc || '', nFotos: raw.g || (raw.img ? 1 : 0),
    outras: Array.isArray(raw.o) ? raw.o.filter((o) => Array.isArray(o) && o[0]) : [],
    q: raw.q || null, ag: raw.ag || [], orgao: (raw.ag || []).map((a) => ctx.orgaos?.[a]).find(Boolean) || '', rd: raw.rd || '', vq: raw.vq || 0, cidade: uf ? raw.cid || '' : '', polo: raw.fr || '', prioridadeFr: raw.frp || 9, oficial: Boolean(raw.fp),
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
const pontos = (n) => (n.texto ? 8 : 0) + Math.min(n.nFotos || 0, 5) * 2 + (n.temLink ? 3 : 0) + (n.uf ? 1 : 0) + (n.resumo ? 1 : 0);
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
export function carregarFeed(arquivo = 'feed.json', { novo = false } = {}) {
  if (!novo && feeds.has(arquivo)) return feeds.get(arquivo);
  // novo: busca de novo no servidor (atualização da página aberta), sem o cache do navegador.
  const feedPromise = buscarDados(novo ? `${arquivo}?t=${Date.now()}` : arquivo, novo ? { cache: 'no-store' } : {}).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).then((dados) => {
    const ctx = {
      categorias: dados.categorias || [], orgaos: dados.orgaos || [], materiais: dados.materiais || {},
      atualizado: dados.atualizado_em ? new Date(dados.atualizado_em) : null,
    };
    ctx.noticias = deduplicar((dados.noticias || []).map((n) => preparar(n, ctx)))
      .sort((a, b) => (b.data?.getTime() || 0) - (a.data?.getTime() || 0));
    ctx.porIndice = new Map(ctx.noticias.map((n) => [n.i, n]));
    ctx.parcial = Boolean(dados.parcial);
    ctx.recorte = dados.recorte || '';  // feed parcial: notícias a partir desta data (o resto em anos/)
    return ctx;
  });
  if (!novo) feeds.set(arquivo, feedPromise);
  return feedPromise;
}

/** anos/indice.json: contagens por ano e mês do acervo inteiro e a data de corte do feed.json. */
let indicePromise = null;
export const indiceAnos = () => (indicePromise ??= buscarDados('anos/indice.json').then((r) => (r.ok ? r.json() : null)).catch(() => null));

/**
 * O feed.json traz só os últimos meses; os anos anteriores ficam em anos/AAAA.json e entram
 * no mesmo contexto quando o leitor pede (filtro de ano, busca em todo o acervo, Observatório).
 * anos: lista de anos (números ou textos); devolve o ctx com as notícias somadas.
 */
const anosCarregando = new Map();
export async function carregarAnos(ctx, anos, aoProgresso) {
  const indice = await indiceAnos();
  const arquivos = new Set(indice?.arquivos || []);
  const faltam = [...new Set(anos.map(String))].filter((a) => arquivos.has(a) && !(ctx.anosCarregados ??= new Set()).has(a));
  let feitos = 0;
  await Promise.all(faltam.map((a) => {
    if (!anosCarregando.has(a)) {
      anosCarregando.set(a, buscarDados(`anos/${a}.json`).then((r) => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }));
    }
    return anosCarregando.get(a).then((dados) => {
      if (ctx.anosCarregados.has(a)) return;
      ctx.anosCarregados.add(a);
      for (const raw of dados.noticias || []) {
        if (ctx.porIndice.has(raw.i)) continue;
        const n = preparar(raw, ctx);
        ctx.noticias.push(n);
        ctx.porIndice.set(n.i, n);
      }
      aoProgresso?.(++feitos, faltam.length);
    }).catch(() => { anosCarregando.delete(a); });
  }));
  if (faltam.length) ctx.noticias.sort((a, b) => (b.data?.getTime() || 0) - (a.data?.getTime() || 0));
  return ctx;
}
/** Anos que estão (ao menos em parte) fora do feed.json. */
export async function anosForaDoFeed() {
  const indice = await indiceAnos();
  return (indice?.arquivos || []).map(Number);
}

// ---------- cabeçalho comum ----------
export function iniciarCabecalho(ctxPromise) {
  const hoje = new Date().toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Sao_Paulo' });
  if ($('hoje')) $('hoje').textContent = hoje.charAt(0).toUpperCase() + hoje.slice(1);
  ctxPromise.then((ctx) => {
    if (!$('atualizado') || !ctx.atualizado) return;
    $('atualizado').textContent = `Atualizado ${relativo(ctx.atualizado)} · ${num(ctx.noticias.length)} notícias`;
    indiceAnos().then((ind) => {  // total do acervo inteiro (todos os anos)
      if (ind?.total) $('atualizado').textContent = `Atualizado ${relativo(ctx.atualizado)} · ${num(ind.total)} notícias`;
    });
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
