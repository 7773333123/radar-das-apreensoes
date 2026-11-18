/* Observatório: KPIs, mapa, evolução, rankings e maiores apreensões, com filtros na URL. */
import { $, esc, num, qtd, dataBR, ESTADOS, NOME_UF, carregarFeed, carregarAnos, anosForaDoFeed, indiceAnos, iniciarCabecalho, renderMapa, ranking, serie, urlNoticia } from './core.js';
import { iniciarLeitor } from './leitor.js';

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const MESES_L = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const METRICAS = {
  n: { nome: 'Notícias', un: 'n', valor: () => 1 },
  coc: { nome: 'Cocaína', un: 'kg', valor: (n) => n.q?.coc || 0 },
  mac: { nome: 'Maconha e skunk', un: 'kg', valor: (n) => (n.q?.mac || 0) + (n.q?.skh || 0) },
  arm: { nome: 'Armas de fogo', un: 'un', valor: (n) => n.q?.arm || 0 },
  mun: { nome: 'Munições', un: 'un', valor: (n) => n.q?.mun || 0 },
};
const st = { ctx: null, f: { p: '6m', uf: '', cat: '', org: '', m: 'n' } };
const fmt = (m, v) => (METRICAS[m].un === 'n' ? `${num(v)} ${v === 1 ? 'notícia' : 'notícias'}` : qtd(v, METRICAS[m].un));

function periodo(p) {
  const agora = new Date();
  const ini = (meses) => new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - meses + 1, 1));
  if (p === '30d') return { ini: new Date(Date.now() - 30 * 86400000), fim: agora, diario: true, nome: 'últimos 30 dias' };
  // 6 meses: o mesmo período do feed.json (não precisa baixar nenhum ano à parte).
  if (p === '6m') return { ini: st.ctx?.recorte ? new Date(st.ctx.recorte + 'T00:00:00Z') : ini(6), fim: agora, nome: 'últimos 6 meses' };
  if (p === '12m') return { ini: ini(12), fim: agora, nome: 'últimos 12 meses' };
  if (p === '24m') return { ini: ini(24), fim: agora, nome: 'últimos 24 meses' };
  if (/^\d{4}$/.test(p)) return { ini: new Date(Date.UTC(+p, 0, 1)), fim: new Date(Date.UTC(+p + 1, 0, 1) - 1), nome: p };
  return { ini: new Date(Date.UTC(2006, 0, 1)), fim: agora, nome: 'todo o acervo' };
}

function lerHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  const f = { ...st.f };
  if (h.get('p')) f.p = h.get('p');
  if (NOME_UF[h.get('uf')]) f.uf = h.get('uf');
  if (/^\d+$/.test(h.get('cat') || '')) f.cat = h.get('cat');
  if (/^\d+$/.test(h.get('org') || '')) f.org = h.get('org');
  if (METRICAS[h.get('m')]) f.m = h.get('m');
  return f;
}
function escreverHash() {
  const h = new URLSearchParams();
  for (const [k, v] of Object.entries(st.f)) if (v && !(k === 'p' && v === '6m') && !(k === 'm' && v === 'n')) h.set(k, v);
  history.replaceState(history.state, '', h.toString() ? '#' + h : location.pathname);
}
function definir(parcial) { Object.assign(st.f, parcial); escreverHash(); garantirPeriodo().then(render); }
// O feed.json traz os últimos 6 meses; períodos mais longos carregam os anos que faltam (anos/AAAA.json).
async function garantirPeriodo() {
  const per = periodo(st.f.p);
  if (st.ctx.recorte && per.ini >= new Date(st.ctx.recorte + 'T00:00:00Z')) return;  // cabe no feed.json
  const fora = await anosForaDoFeed();
  const precisa = fora.filter((a) => a >= per.ini.getUTCFullYear() && a <= per.fim.getUTCFullYear() &&
    !(st.ctx.anosCarregados || new Set()).has(String(a)));
  if (!precisa.length) return;
  $('oKpis').innerHTML = `<p class="note">Carregando ${precisa.length === 1 ? `as notícias de ${precisa[0]}` : `${precisa.length} anos do acervo`}…</p>`;
  await carregarAnos(st.ctx, precisa, (feitos, total) => {
    if (total > 1) $('oKpis').innerHTML = `<p class="note">Carregando o acervo… ${feitos}/${total} anos</p>`;
  });
}

function render() {
  const { ctx, f } = st;
  const per = periodo(f.p), M = METRICAS[f.m];
  const noPeriodo = ctx.noticias.filter((n) => n.data && n.data >= per.ini && n.data <= per.fim &&
    (f.cat === '' || n.cats.includes(+f.cat)) && (f.org === '' || n.ag.includes(+f.org)));
  const sel = noPeriodo.filter((n) => !f.uf || n.uf === f.uf);
  const local = f.uf ? NOME_UF[f.uf] : 'Brasil';

  // Controles
  $('oPeriodo').value = f.p; $('oEstado').value = f.uf; $('oTipo').value = f.cat; $('oOrgao').value = f.org;
  $('oMetricas').innerHTML = Object.entries(METRICAS).map(([k, m]) => `<button type="button" class="chip" data-m="${k}" aria-pressed="${k === f.m}">${esc(m.nome)}</button>`).join('');

  // KPIs
  const soma = (fn) => sel.reduce((s, n) => s + fn(n), 0);
  const comQ = (fn) => sel.filter((n) => fn(n) > 0).length;
  const fontes = new Set(sel.flatMap((n) => [n.fonte, ...n.outras.map((o) => o[0])]));
  const kpi = (rotulo, valor, sub) => `<div class="kpi"><dt>${esc(rotulo)}</dt><dd>${valor}</dd>${sub ? `<div class="sub">${esc(sub)}</div>` : ''}</div>`;
  $('oKpis').innerHTML =
    kpi('Notícias', num(sel.length), `${local} · ${per.nome}`) +
    kpi('Cocaína', '≈ ' + qtd(soma(METRICAS.coc.valor), 'kg'), `em ${num(comQ(METRICAS.coc.valor))} notícias`) +
    kpi('Maconha e skunk', '≈ ' + qtd(soma(METRICAS.mac.valor), 'kg'), `em ${num(comQ(METRICAS.mac.valor))} notícias`) +
    kpi('Armas de fogo', '≈ ' + qtd(soma(METRICAS.arm.valor), 'un'), `em ${num(comQ(METRICAS.arm.valor))} notícias`) +
    kpi('Munições', '≈ ' + qtd(soma(METRICAS.mun.valor), 'un'), `em ${num(comQ(METRICAS.mun.valor))} notícias`) +
    kpi('Veículos e órgãos', num(fontes.size), 'fontes distintas');

  // Mapa e ranking de estados (no período, todos os estados; o selecionado fica marcado)
  const porUf = {};
  noPeriodo.forEach((n) => { if (n.uf) porUf[n.uf] = (porUf[n.uf] || 0) + M.valor(n); });
  $('oMapaTitulo').textContent = `${M.nome} por estado · ${per.nome}`;
  $('oRankUfTitulo').textContent = `Estados · ${M.nome.toLowerCase()}`;
  renderMapa($('oMapa'), porUf, { sel: f.uf, rotulo: `${M.nome} por estado`, formato: (v) => fmt(f.m, v), aoClicar: (uf) => definir({ uf: f.uf === uf ? '' : uf }) });
  ranking($('oRankUf'), Object.entries(porUf).sort((a, b) => b[1] - a[1]).map(([uf, v]) => [uf, v, NOME_UF[uf]]),
    { attr: 'data-uf', sel: f.uf, formato: (v) => fmt(f.m, v), max: 27 });

  // Evolução (diária em 30 dias; mensal nos demais)
  const pontos = [];
  if (per.diario) {
    for (let d = 29; d >= 0; d--) {
      const dia = new Date(Date.now() - d * 86400000);
      const k = dia.toISOString().slice(0, 10);
      pontos.push({ k, curto: `${dia.getUTCDate()}/${dia.getUTCMonth() + 1}`, longo: dataBR(dia), v: 0 });
    }
  } else {
    const ini = sel.length && f.p === 'tudo' ? new Date(Math.max(per.ini, sel.reduce((m, n) => Math.min(m, n.data.getTime()), Infinity))) : per.ini;
    for (let d = new Date(Date.UTC(ini.getUTCFullYear(), ini.getUTCMonth(), 1)); d <= per.fim; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
      pontos.push({ k: d.toISOString().slice(0, 7), curto: `${MESES[d.getUTCMonth()]}${d.getUTCMonth() === 0 || pontos.length === 0 ? '/' + String(d.getUTCFullYear()).slice(2) : ''}`, longo: `${MESES_L[d.getUTCMonth()]} de ${d.getUTCFullYear()}`, v: 0 });
    }
  }
  const idx = new Map(pontos.map((p, k) => [p.k, k]));
  sel.forEach((n) => { const k = idx.get(n.data.toISOString().slice(0, per.diario ? 10 : 7)); if (k != null) pontos[k].v += M.valor(n); });
  $('oSerieTitulo').textContent = `${M.nome} · ${local} · ${per.diario ? 'por dia' : 'por mês'}`;
  serie($('oSerie'), pontos, { formato: (v) => fmt(f.m, v), rotulo: `${M.nome} ao longo do tempo` });
  $('oSerieTabela').innerHTML = `<table><thead><tr><th>${per.diario ? 'Dia' : 'Mês'}</th><th>${esc(M.nome)}</th></tr></thead><tbody>` +
    pontos.map((p) => `<tr><td>${esc(p.longo)}</td><td>${esc(fmt(f.m, p.v))}</td></tr>`).join('') + '</tbody></table>';

  // Rankings secundários
  const conta = (chaves) => { const m = new Map(); sel.forEach((n) => chaves(n).forEach((k) => m.set(k, (m.get(k) || 0) + M.valor(n)))); return [...m].sort((a, b) => b[1] - a[1]); };
  ranking($('oRankOrgao'), conta((n) => n.ag).map(([k, v]) => [String(k), v, ctx.orgaos[k]]), { attr: 'data-org', sel: f.org, formato: (v) => fmt(f.m, v) });
  ranking($('oRankRod'), conta((n) => (n.rd ? [n.rd] : [])).map(([k, v]) => [k, v, k]), { formato: (v) => fmt(f.m, v) });
  ranking($('oRankTipo'), conta((n) => n.cats).map(([k, v]) => [String(k), v, ctx.categorias[k]]), { attr: 'data-cat', sel: f.cat, formato: (v) => fmt(f.m, v) });

  // Maiores apreensões (ou matérias mais repercutidas, no indicador "Notícias")
  const top = f.m === 'n'
    ? [...sel].filter((n) => n.outras.length).sort((a, b) => b.outras.length - a.outras.length || b.data - a.data).slice(0, 10)
    : [...sel].filter((n) => M.valor(n) > 0).sort((a, b) => M.valor(b) - M.valor(a)).slice(0, 10);
  $('oTopTitulo').textContent = f.m === 'n' ? 'Matérias mais repercutidas' : `Maiores apreensões de ${M.nome.toLowerCase()} noticiadas`;
  $('oTop').innerHTML = top.length ? top.map((n) =>
    `<li><a href="${urlNoticia(n)}" data-read="${n.i}"><span class="q">${esc(f.m === 'n' ? `${n.outras.length + 1} veículos` : qtd(M.valor(n), M.un))}</span>` +
    `<span><span class="t">${esc(n.titulo)}</span><br><span class="m">${esc(dataBR(n.data))} · ${esc(n.uf ? NOME_UF[n.uf] : 'Estado não identificado')} · ${esc(n.fonte)}</span></span></a></li>`).join('')
    : '<li class="note">Sem registros para este recorte.</li>';
}

async function iniciar() {
  const promessa = carregarFeed();
  iniciarCabecalho(promessa);
  try { st.ctx = await promessa; } catch (e) { $('oKpis').innerHTML = '<p class="empty">Não foi possível carregar os dados.</p>'; return; }
  const ind = await indiceAnos();
  const anos = [...new Set([...Object.keys(ind?.anos || {}).map(Number), ...st.ctx.noticias.map((n) => n.ano)])]
    .filter((a) => a >= 2006).sort((a, b) => b - a);
  $('oPeriodo').innerHTML = [['30d', 'Últimos 30 dias'], ['6m', 'Últimos 6 meses'], ['12m', 'Últimos 12 meses'], ['24m', 'Últimos 24 meses'], ...anos.map((a) => [String(a), String(a)]), ['tudo', 'Todo o acervo']]
    .map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
  $('oEstado').insertAdjacentHTML('beforeend', ESTADOS.map(([uf, n]) => `<option value="${uf}">${esc(n)}</option>`).join(''));
  $('oTipo').insertAdjacentHTML('beforeend', st.ctx.categorias.map((c, k) => `<option value="${k}">${esc(c)}</option>`).join(''));
  $('oOrgao').insertAdjacentHTML('beforeend', st.ctx.orgaos.map((o, k) => `<option value="${k}">${esc(o)}</option>`).join(''));
  $('oPeriodo').addEventListener('change', (e) => definir({ p: e.target.value }));
  $('oEstado').addEventListener('change', (e) => definir({ uf: e.target.value }));
  $('oTipo').addEventListener('change', (e) => definir({ cat: e.target.value }));
  $('oOrgao').addEventListener('change', (e) => definir({ org: e.target.value }));
  $('oLimpar').addEventListener('click', () => definir({ p: '6m', uf: '', cat: '', org: '' }));
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-m],[data-uf],[data-cat],[data-org]');
    if (!b || b.tagName !== 'BUTTON') return;
    if (b.dataset.m) return definir({ m: b.dataset.m });
    if (b.dataset.uf) return definir({ uf: st.f.uf === b.dataset.uf ? '' : b.dataset.uf });
    if (b.dataset.cat) return definir({ cat: st.f.cat === b.dataset.cat ? '' : b.dataset.cat });
    if (b.dataset.org) return definir({ org: st.f.org === b.dataset.org ? '' : b.dataset.org });
  });
  st.f = lerHash();
  render();
  iniciarLeitor(st.ctx);
  garantirPeriodo().then(render);
}
iniciar();
