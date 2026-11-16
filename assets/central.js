/* Central de notícias: manchete, destaques, Em alta, panorama, editorias e busca. */
import { $, esc, num, fold, debounce, relativo, horaBR, qtd, ESTADOS, NOME_UF, CURTO, carregarFeed, iniciarCabecalho, midia, renderMapa, ranking, urlNoticia } from './core.js';
import { iniciarLeitor, kickerHTML, metaHTML } from './leitor.js';

const POR_PAGINA = 20;
const DIA = 86400000;
const st = { ctx: null, filtro: { q: '', uf: '', cat: '', ano: '' }, lista: [], limite: POR_PAGINA };

// ---------- blocos de matéria ----------
const story = (n, { dek = false, img = true, cont = false } = {}) =>
  `<a class="story" href="${urlNoticia(n)}" data-read="${n.i}">${img ? midia(n, { contador: cont }) : ''}` +
  `${kickerHTML(n, st.ctx, st.filtro.cat || null)}<h3 class="headline">${esc(n.titulo)}</h3>${dek && n.resumo ? `<p class="dek">${esc(n.resumo)}</p>` : ''}${metaHTML(n)}</a>`;
const linha = (n) => `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><div>${kickerHTML(n, st.ctx, st.filtro.cat || null)}` +
  `<h3 class="headline">${esc(n.titulo)}</h3>${n.resumo ? `<p class="dek">${esc(n.resumo)}</p>` : ''}${metaHTML(n)}</div>${midia(n)}</a></li>`;

// ---------- filtros na URL (compatível com links antigos) ----------
function lerHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  // Busca vinda das páginas próprias (/?q=...): passa para o formato da Central.
  const busca = new URLSearchParams(location.search).get('q');
  if (busca && !p.get('q')) p.set('q', busca);
  const legado = location.hash.match(/^#estado-(.+)$/);
  let uf = (p.get('uf') || '').toUpperCase();
  if (legado) { const v = decodeURIComponent(legado[1]); uf = NOME_UF[v.toUpperCase()] ? v.toUpperCase() : (ESTADOS.find(([, n]) => n === v) || [''])[0]; }
  const cat = p.get('cat') ?? '';
  return { q: p.get('q') || '', uf: NOME_UF[uf] ? uf : '', cat: /^\d$/.test(cat) ? cat : '', ano: /^\d{4}$/.test(p.get('ano') || '') ? p.get('ano') : '' };
}
function escreverHash() {
  const p = new URLSearchParams();
  for (const k of ['q', 'uf', 'cat', 'ano']) if (st.filtro[k]) p.set(k, st.filtro[k]);
  const h = p.toString();
  history.replaceState(history.state, '', h ? '#' + h : location.pathname);
}
const temFiltro = () => Object.values(st.filtro).some(Boolean);
function definir(parcial, { rolar = true } = {}) {
  Object.assign(st.filtro, parcial);
  st.limite = POR_PAGINA;
  render();
  escreverHash();
  if (rolar) (temFiltro() ? $('resultados') : $('conteudo')).scrollIntoView({ block: 'start' });
}

// ---------- página inicial ----------
function renderInicio() {
  const ns = st.ctx.noticias, agora = Date.now();
  const recentes = (dias) => ns.filter((n) => n.data && agora - n.data.getTime() <= dias * DIA && n.data.getTime() <= agora + 3600000);

  // Faixa "Agora": as mais recentes, com hora.
  $('agora').innerHTML = ns.slice(0, 12).map((n) =>
    `<li><button type="button" data-read="${n.i}"><time>${esc(agora - (n.data?.getTime() || 0) < DIA ? horaBR(n.data) : relativo(n.data))}</time>${esc(n.titulo)}</button></li>`).join('');
  $('agoraFaixa').hidden = false;

  // Importância da notícia (manchete e "Em alta"):
  // - tamanho da apreensão (escala logarítmica: 1 t de droga pesa mais que 10 kg);
  // - repercussão (quantos veículos publicaram);
  // - apreensão concreta no título; notícias de soltura, julgamento ou
  //   desdobramento judicial perdem peso;
  // - prazo de validade: a nota cai pela metade a cada 12 horas, então a
  //   manchete é sempre do dia, mas a mais importante do dia fica no topo.
  const horas = (n) => Math.max(0, (agora - (n.data?.getTime() || 0)) / 3600000);
  const log = (v) => Math.log10(1 + (v || 0));
  const importancia = (n) => {
    const q = n.q || {};
    const drogas = (q.coc || 0) + (q.mac || 0) + (q.skh || 0) + (q.cra || 0) + (q.dro || 0);
    let p = 1;
    p += log(drogas) * 1.6;                       // 100 kg ≈ 3,2; 1 t ≈ 4,8
    p += log(q.arm) * 2 + log(q.fuz) * 2.5;       // armas e, sobretudo, fuzis
    p += log(q.mun) * 0.8;
    p += Math.min(n.outras.length, 10) * 0.6;     // repercussão
    if (/apreen|apreend|confisc/i.test(n.titulo)) p += 1;
    if (/\b(PF|PRF|Receita Federal|Pol[ií]cia Federal|FICCO|Gaeco)\b|opera[çc][ãa]o/i.test(n.titulo)) p += 0.5;
    if (/\b(solta|soltura|liberad[oa]|absolvid|julgament|condenad|habeas|den[uú]ncia|audi[êe]ncia|foragid)/i.test(n.titulo)) p -= 2;
    return Math.max(0.2, p);
  };
  const nota = (n) => importancia(n) * Math.pow(0.5, horas(n) / 12);
  const comFoto = ns.filter((n) => n.img && n.data && n.data.getTime() <= agora + 3600000);
  const janela = (h) => comFoto.filter((n) => horas(n) <= h);
  const pool = [24, 48].map(janela).find((l) => l.length >= 5) || comFoto.slice(0, 20);
  const manchete = [...pool].sort((a, b) => nota(b) - nota(a) || b.data - a.data)[0] || ns[0];
  const usados = new Set([manchete]);
  // Ao lado da manchete: as mais recentes com foto, em ordem cronológica.
  const lado = pool.filter((n) => !usados.has(n)).sort((a, b) => b.data - a.data).slice(0, 4);
  lado.forEach((n) => usados.add(n));

  // Em alta: publicadas por mais veículos nas últimas 24 h (ou 48 h, se houver poucas).
  const repercutidas = (h) => recentes(h / 24).filter((n) => n.outras.length && !usados.has(n));
  const alta = (repercutidas(24).length >= 3 ? repercutidas(24) : repercutidas(48))
    .sort((a, b) => nota(b) - nota(a) || b.data - a.data).slice(0, 5);

  // Panorama de 30 dias (apreensões noticiadas).
  const r30 = recentes(30);
  const soma = (k) => r30.reduce((s, n) => s + (n.q?.[k] || 0), 0);
  const porUf = {};
  r30.forEach((n) => { if (n.uf) porUf[n.uf] = (porUf[n.uf] || 0) + 1; });

  // Editorias: os tipos mais noticiados em 30 dias.
  const porCat = new Map();
  r30.forEach((n) => n.cats.forEach((c) => { if (c !== 8) porCat.set(c, (porCat.get(c) || []).concat(n)); }));
  const editorias = [...porCat].sort((a, b) => b[1].length - a[1].length).slice(0, 4);

  $('inicio').innerHTML =
    `<section class="lead" aria-label="Destaques">` +
      `<div class="lead-main">${story(manchete, { dek: true, cont: true }).replace('<h3 class="headline">', '<h2 class="headline">').replace('</h3>', '</h2>')}</div>` +
      `<div class="lead-side">${lado.map((n) => `<a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><div>${kickerHTML(n, st.ctx)}<h3 class="headline">${esc(n.titulo)}</h3>${metaHTML(n)}</div>${midia(n)}</a>`).join('')}</div>` +
    `</section>` +
    `<div class="section-head"><h2>Em alta e em números</h2><a href="observatorio">Abrir o Observatório →</a></div>` +
    `<section class="band">` +
      `<div class="panel"><h3>Em alta</h3>${alta.length ? `<ol class="trend">${alta.map((n) =>
        `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><h4 class="headline">${esc(n.titulo)}</h4><div class="meta"><span class="sources">${n.outras.length + 1} veículos</span> · ${esc(relativo(n.data))}</div></a></li>`).join('')}</ol>`
        : '<p class="note">Sem matérias repercutidas nas últimas 48 horas.</p>'}<p class="note">Matérias publicadas por mais veículos nas últimas 24 horas.</p></div>` +
      `<div class="panel"><h3>Últimos 30 dias</h3><dl class="kpis">` +
        `<div class="kpi"><dt>Notícias</dt><dd>${num(r30.length)}</dd></div>` +
        `<div class="kpi"><dt>Cocaína</dt><dd>${qtd(soma('coc'), 'kg')}</dd></div>` +
        `<div class="kpi"><dt>Maconha e skunk</dt><dd>${qtd(soma('mac') + soma('skh'), 'kg')}</dd></div>` +
        `<div class="kpi"><dt>Armas de fogo</dt><dd>${qtd(soma('arm'), 'un')}</dd></div>` +
      `</dl><p class="note">Quantidades citadas nas notícias, sem duplicatas. Não são estatísticas oficiais.</p></div>` +
      `<div class="panel"><h3>Notícias por estado · 30 dias</h3><div class="map" id="mapaInicio"></div></div>` +
    `</section>` +
    `<div class="editorias">${editorias.map(([c, itens]) => {
      // Cada matéria aparece em uma só editoria da página inicial.
      const livres = itens.filter((n) => !usados.has(n));
      const primeira = livres.find((n) => n.img) || livres[0] || itens[0];
      usados.add(primeira);
      const resto = livres.filter((n) => n !== primeira && !usados.has(n)).slice(0, 3);
      resto.forEach((n) => usados.add(n));
      return `<section class="editoria"><div class="section-head"><h2>${esc(st.ctx.categorias[c])}</h2><a href="#cat=${c}" data-cat="${c}">Ver tudo →</a></div>` +
        `<div class="first"><a class="story" href="${urlNoticia(primeira)}" data-read="${primeira.i}">${midia(primeira)}<div>${kickerHTML(primeira, st.ctx, c)}<h3 class="headline">${esc(primeira.titulo)}</h3>${metaHTML(primeira)}</div></a></div>` +
        `<ul>${resto.map((n) => `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><h3 class="headline">${esc(n.titulo)}</h3>${metaHTML(n)}</a></li>`).join('')}</ul></section>`;
    }).join('')}</div>`;
  renderMapa($('mapaInicio'), porUf, { rotulo: 'Notícias por estado nos últimos 30 dias', formato: (v) => `${num(v)} notícias`, aoClicar: (uf) => definir({ uf }) });
}

// ---------- lista e filtros ----------
function filtrar() {
  const { q, uf, cat, ano } = st.filtro;
  const termos = fold(q).split(/\s+/).filter(Boolean);
  const c = cat === '' ? -1 : Number(cat);
  return st.ctx.noticias.filter((n) => (!uf || n.uf === uf) && (c < 0 || n.cats.includes(c)) &&
    (!ano || String(n.ano) === ano) && termos.every((t) => n.busca.includes(t)));
}
function render() {
  const f = st.filtro, filtrado = temFiltro();
  $('inicio').hidden = filtrado;
  $('agoraFaixa').hidden = filtrado;
  st.lista = filtrar();
  const partes = [f.cat !== '' ? st.ctx.categorias[f.cat] : '', f.uf ? NOME_UF[f.uf] : '', f.ano, f.q ? `“${f.q}”` : ''].filter(Boolean);
  $('resTitulo').textContent = filtrado ? partes.join(' · ') : 'Últimas notícias';
  $('contagem').innerHTML = `<b>${num(st.lista.length)}</b> ${st.lista.length === 1 ? 'notícia' : 'notícias'}`;
  $('lista').innerHTML = st.lista.length ? st.lista.slice(0, st.limite).map(linha).join('')
    : '<li class="empty">Nenhuma notícia encontrada. Tente outro termo ou remova um filtro.</li>';
  $('mais').hidden = st.limite >= st.lista.length;
  $('limpar').hidden = !filtrado;
  $('fEstado').value = f.uf; $('fCategoria').value = f.cat; $('fAno').value = f.ano;
  if ($('buscaTopo').value !== f.q) $('buscaTopo').value = f.q;
  document.querySelectorAll('#editorias a').forEach((a) => a.setAttribute('aria-current', String((a.dataset.cat ?? '') === f.cat && !f.q)));
  const sel = $('selEstado'); if (sel) sel.value = f.uf;
  // Painel lateral: refinar dentro do resultado atual.
  const porUf = {}, porCat = new Map();
  st.lista.forEach((n) => { if (n.uf) porUf[n.uf] = (porUf[n.uf] || 0) + 1; n.cats.forEach((c) => porCat.set(c, (porCat.get(c) || 0) + 1)); });
  renderMapa($('mapaLado'), porUf, { sel: f.uf, rotulo: 'Notícias do resultado por estado', formato: (v) => `${num(v)} notícias`, aoClicar: (uf) => definir({ uf: f.uf === uf ? '' : uf }) });
  ranking($('rankTipos'), [...porCat].sort((a, b) => b[1] - a[1]).map(([c, v]) => [String(c), v, st.ctx.categorias[c]]), { attr: 'data-cat', sel: f.cat });
}

function montarControles() {
  $('editorias').innerHTML = `<a href="./" data-cat="">Todas</a>` +
    st.ctx.categorias.map((c, k) => `<a href="#cat=${k}" data-cat="${k}">${esc(CURTO[k] || c)}</a>`).join('') +
    `<span class="sep" aria-hidden="true"></span><label class="sr" for="selEstado">Estado</label><select id="selEstado"><option value="">Todos os estados</option>${ESTADOS.map(([uf, n]) => `<option value="${uf}">${esc(n)}</option>`).join('')}</select>`;
  $('fEstado').insertAdjacentHTML('beforeend', ESTADOS.map(([uf, n]) => `<option value="${uf}">${esc(n)}</option>`).join(''));
  $('fCategoria').insertAdjacentHTML('beforeend', st.ctx.categorias.map((c, k) => `<option value="${k}">${esc(c)}</option>`).join(''));
  const anos = [...new Set(st.ctx.noticias.map((n) => n.ano).filter(Boolean))].sort((a, b) => b - a);
  $('fAno').insertAdjacentHTML('beforeend', anos.map((a) => `<option value="${a}">${a}</option>`).join(''));

  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-cat]');
    if (!a || e.target.closest('[data-read]')) return;
    e.preventDefault();
    const c = a.dataset.cat;
    definir(a.closest('#editorias') ? { cat: c, q: '' } : { cat: st.filtro.cat === c ? '' : c });
  });
  $('selEstado').addEventListener('change', (e) => definir({ uf: e.target.value }));
  $('fEstado').addEventListener('change', (e) => definir({ uf: e.target.value }, { rolar: false }));
  $('fCategoria').addEventListener('change', (e) => definir({ cat: e.target.value }, { rolar: false }));
  $('fAno').addEventListener('change', (e) => definir({ ano: e.target.value }, { rolar: false }));
  $('limpar').addEventListener('click', () => definir({ q: '', uf: '', cat: '', ano: '' }));
  $('mais').addEventListener('click', () => { st.limite += POR_PAGINA; render(); });
  $('formBusca').addEventListener('submit', (e) => { e.preventDefault(); definir({ q: $('buscaTopo').value.trim() }); });
  $('buscaTopo').addEventListener('input', debounce((e) => { if (e.target.value.trim().length !== 1) definir({ q: e.target.value.trim() }, { rolar: false }); }, 250));
  window.addEventListener('hashchange', () => {
    if (/^#noticia-/.test(location.hash)) return;
    const h = lerHash();
    if (['q', 'uf', 'cat', 'ano'].some((k) => h[k] !== st.filtro[k])) definir(h, { rolar: false });
  });
}

async function iniciar() {
  const promessa = carregarFeed();
  iniciarCabecalho(promessa);
  $('lista').innerHTML = '<li><div class="sk" style="height:120px;margin:18px 0"></div></li>'.repeat(4);
  try {
    st.ctx = await promessa;
  } catch (err) {
    console.error(err);
    $('lista').innerHTML = '<li class="empty">Não foi possível carregar as notícias. Verifique a conexão e recarregue a página.</li>';
    return;
  }
  montarControles();
  Object.assign(st.filtro, lerHash());
  renderInicio();
  render();
  iniciarLeitor(st.ctx);
}
iniciar();
