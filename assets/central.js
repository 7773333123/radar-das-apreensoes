/* Central de notícias: manchete, destaques, Em alta, panorama, editorias e busca. */
import { $, esc, num, fold, debounce, relativo, horaBR, qtd, ESTADOS, NOME_UF, CURTO, carregarFeed, carregarAnos, anosForaDoFeed, indiceAnos, iniciarCabecalho, midia, renderMapa, ranking, urlNoticia } from './core.js';
import { iniciarLeitor, kickerHTML, metaHTML } from './leitor.js';

const POR_PAGINA = 20;
const DIA = 86400000;
const st = { ctx: null, filtro: { q: '', uf: '', cat: '', ano: '' }, lista: [], limite: POR_PAGINA };

// ---------- blocos de matéria ----------
// Linha fina curta: só o começo do resumo do veículo, cortado no fim de uma palavra.
const curto = (t, max = 180) => (t.length <= max ? t : t.slice(0, max).replace(/\s+\S*$/, '') + '…');
const story = (n, { dek = false, img = true, cont = false } = {}) =>
  `<a class="story" href="${urlNoticia(n)}" data-read="${n.i}">${img ? midia(n, { contador: cont }) : ''}` +
  `${kickerHTML(n, st.ctx, st.filtro.cat || null)}<h3 class="headline">${esc(n.titulo)}</h3>${dek && n.resumo ? `<p class="dek">${esc(curto(n.resumo))}</p>` : ''}${metaHTML(n)}</a>`;
const linha = (n) => `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><div>${kickerHTML(n, st.ctx, st.filtro.cat || null)}` +
  `<h3 class="headline">${esc(n.titulo)}</h3>${n.resumo ? `<p class="dek">${esc(curto(n.resumo, 120))}</p>` : ''}${metaHTML(n)}</div>${midia(n)}</a></li>`;

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
  escreverHash();
  garantirAno().then(() => {
    render();
    if (rolar) (temFiltro() ? $('resultados') : $('conteudo')).scrollIntoView({ block: 'start' });
  });
  render();
}
// O feed.json traz os últimos 6 meses; um ano anterior é carregado quando escolhido no filtro.
async function garantirAno() {
  const ano = Number(st.filtro.ano);
  if (!ano || !st.ctx || (st.ctx.anosCarregados || new Set()).has(String(ano))) return;
  if (!(await anosForaDoFeed()).includes(ano)) return;
  $('lista').innerHTML = `<li class="empty">Carregando as notícias de ${ano}…</li>`;
  await carregarAnos(st.ctx, [ano]);
}
// Busca em todo o acervo (todos os anos), a pedido do leitor.
async function buscarTudo(botao) {
  const anos = await anosForaDoFeed();
  botao.disabled = true;
  await carregarAnos(st.ctx, anos, (feitos, total) => { botao.textContent = `Carregando o acervo… ${feitos}/${total} anos`; });
  st.tudo = true;
  render();
}

// ---------- faixa "Agora": as mais recentes, em duas linhas rolando sem parar ----------
// As linhas andam sozinhas (param quando o leitor passa o mouse ou toca nelas). A página confere
// agora.json (poucos KB) a cada minuto; se chegou notícia, busca o feed e atualiza na hora.
let agoraAssinatura = '';
function renderAgora(ns, agora) {
  // Só o que é de agora: as das últimas 3 horas (no mínimo 10 notícias; se faltar, amplia até 6, 12 e 24 horas).
  const validas = ns.filter((n) => n.data && n.data.getTime() <= agora + 3600000);
  const ate = (h) => validas.filter((n) => agora - n.data.getTime() <= h * 3600000);
  const itens = ([3, 6, 12, 24].map(ate).find((l) => l.length >= 10) || validas.slice(0, 12)).slice(0, 24);
  const assinatura = itens.map((n) => n.i).join(',');
  if (assinatura === agoraAssinatura && $('agora').childElementCount) return;  // mesmas notícias
  agoraAssinatura = assinatura;
  const li = (n, copia) => `<li${copia ? ' aria-hidden="true"' : ''}><a href="${urlNoticia(n)}" data-read="${n.i}"${copia ? ' tabindex="-1"' : ''}>` +
    `<time>${esc(agora - (n.data?.getTime() || 0) < DIA ? horaBR(n.data) : relativo(n.data))}</time>${esc(n.titulo)}</a></li>`;
  // Linha 1: 1ª, 3ª, 5ª... mais novas; linha 2: 2ª, 4ª, 6ª... (as duas começam pelas mais recentes).
  const linhas = [itens.filter((_, k) => k % 2 === 0), itens.filter((_, k) => k % 2 === 1)];
  ['agora', 'agora2'].forEach((id, k) => {
    const ol = $(id);
    if (!ol) return;
    const lista = linhas[k].length ? linhas[k] : linhas[0];
    // Duas cópias seguidas: a animação anda metade da largura e recomeça sem salto.
    ol.innerHTML = lista.map((n) => li(n, false)).join('') + lista.map((n) => li(n, true)).join('');
    ol.classList.remove('rolando');
    requestAnimationFrame(() => {
      const metade = ol.scrollWidth / 2;
      // ~55 px por segundo; a 2ª linha um pouco mais lenta, para as duas não andarem coladas.
      ol.style.setProperty('--dur', `${Math.max(30, Math.round(metade / (k ? 48 : 55)))}s`);
      ol.classList.add('rolando');
    });
  });
  $('agoraFaixa').hidden = temFiltro();
}

// Confere a cada minuto se chegou notícia nova (agora.json, poucos KB); só então baixa o feed.
let agoraVistos = '';
async function conferirAgora() {
  if (document.hidden || !st.ctx) return;
  let r;
  try { r = await fetch(`agora.json?t=${Date.now()}`, { cache: 'no-store' }).then((x) => (x.ok ? x.json() : null)); } catch { return; }
  const ids = (r?.noticias || []).map((n) => n.i);
  if (!ids.length) return;
  const assinatura = ids.join(',');
  if (assinatura === agoraVistos) return renderAgora(st.ctx.noticias, Date.now());
  agoraVistos = assinatura;
  if (ids.some((i) => !st.ctx.porIndice.has(i))) await atualizarAoVivo();
}

async function atualizarAoVivo() {
  if (document.hidden || !st.ctx) return;
  let novo;
  try { novo = await carregarFeed('feed-recente.json', { novo: true }); } catch { return; }
  const ctx = st.ctx;
  const chegaram = novo.noticias.filter((n) => !ctx.porIndice.has(n.i));
  // Período coberto pelo feed novo (31 dias): o que não está mais nele foi juntado como
  // duplicata ou retirado do site; sai também da página aberta.
  const ids = new Set(novo.noticias.map((n) => n.i));
  const desde = Math.min(...novo.noticias.map((n) => n.data?.getTime() || Infinity));
  const sairam = ctx.noticias.filter((n) => n.data && n.data.getTime() >= desde && !ids.has(n.i));
  // Versões atualizadas (outras fontes, foto, resumo) das que continuam.
  const mudaram = novo.noticias.filter((n) => ctx.porIndice.has(n.i));
  if (chegaram.length || sairam.length || mudaram.length) {
    for (const n of sairam) ctx.porIndice.delete(n.i);
    for (const n of [...chegaram, ...mudaram]) ctx.porIndice.set(n.i, n);
    const fora = new Set(sairam.map((n) => n.i));
    ctx.noticias = [...chegaram, ...ctx.noticias.filter((n) => !fora.has(n.i)).map((n) => ctx.porIndice.get(n.i) || n)]
      .sort((a, b) => (b.data?.getTime() || 0) - (a.data?.getTime() || 0));
  }
  if (novo.atualizado) {
    ctx.atualizado = novo.atualizado;
    if ($('atualizado')) $('atualizado').textContent = `Atualizado ${relativo(novo.atualizado)} · ${num(ctx.noticias.length)} notícias`;
  }
  if (!chegaram.length && !sairam.length) return renderAgora(ctx.noticias, Date.now());  // as antigas saem da faixa
  // No topo da página, sem leitor aberto e sem filtro: atualiza a página inicial inteira.
  if (!temFiltro() && window.scrollY < 400 && !$('leitor')?.open) { renderInicio(); render(); }
  else renderAgora(ctx.noticias, Date.now());
}

// ---------- página inicial ----------
function renderInicio() {
  const ns = st.ctx.noticias, agora = Date.now();
  const recentes = (dias) => ns.filter((n) => n.data && agora - n.data.getTime() <= dias * DIA && n.data.getTime() <= agora + 3600000);

  renderAgora(ns, agora);

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
    p += Math.min(n.outras.length, 10) * 0.25;    // repercussão (desempata; a quantidade manda)
    if (n.texto) p += 0.3;                        // nota oficial ou texto completo disponível
    if (/apreen|apreend|confisc/i.test(n.titulo)) p += 1;
    if (/\b(PF|PRF|Receita Federal|Pol[ií]cia Federal|FICCO|Gaeco)\b|opera[çc][ãa]o/i.test(n.titulo)) p += 0.5;
    if (/\b(solta|soltura|liberad[oa]|absolvid|julgament|condenad|habeas|den[uú]ncia|audi[êe]ncia|foragid|incinera|destr[oó]i|queima)/i.test(n.titulo)) p -= 2;
    return Math.max(0.2, p);
  };
  // "Adolescente apreendido": apreensão de pessoa (ato infracional), não de material. Fica no site,
  // mas não disputa manchete, destaques nem as principais da Fronteira.
  const SO_PESSOA = /\b(?:adolescentes?|menor(?:es)?(?: de idade)?|jove[mn]s? de 1[0-7] anos|crian[çc]as?)\b[^.]{0,60}?\bapreendid[oa]s?\b|\bapreendid[oa]s?\b[^.]{0,25}?\b(?:adolescentes?|menor(?:es)?)\b|\bapreend(?:e|em|eu|eram)\s+(?:(?:um|uma|dois|duas|tr[êe]s|\d+)\s+)?(?:adolescentes?|menor(?:es)?)\b|ato infracional/i;
  const soPessoa = (n) => SO_PESSOA.test(n.titulo) && !(n.q && Object.keys(n.q).length);
  const nota = (n) => importancia(n) * Math.pow(0.5, horas(n) / 12) * (soPessoa(n) ? 0.3 : 1);
  const tipo = (n) => n.cats[0] ?? 8;
  const tamanho = (n) => {
    const q = n.q || {};
    switch (tipo(n)) {
      case 0: return (q.coc || 0) + (q.mac || 0) + (q.skh || 0) + (q.cra || 0) + (q.dro || 0);   // kg de droga
      case 1: return (q.fuz || 0) * 10 + (q.arm || 0) + (q.mun || 0) / 100;                       // fuzis pesam mais
      default: return n.vq || 0;                                                                   // valor em R$
    }
  };
  const tamanhoNo = (n, c) => tamanho({ ...n, cats: [c] });
  const desdobramento = (n) => /\b(solta|soltura|liberad[oa]|absolvid|julgament|condenad|habeas|den[uú]ncia|audi[êe]ncia|foragid|incinera|destr[oó]i|queima)/i.test(n.titulo);
  const ordemPorTipo = (a, b) => (soPessoa(a) - soPessoa(b)) || (desdobramento(a) - desdobramento(b)) || (tipo(a) - tipo(b)) ||
    (tamanho(b) - tamanho(a)) || (importancia(b) - importancia(a)) || (b.data - a.data);
  const comFoto = ns.filter((n) => n.img && n.data && n.data.getTime() <= agora + 3600000);
  // Destaques = notícias DO DIA (horário de Brasília), da mais relevante para a
  // menos relevante: maior quantidade apreendida primeiro, depois repercussão.
  // Só se o dia ainda tiver menos de 5 com foto (de madrugada), entra a véspera.
  const diaBR = (d) => d.toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
  const hoje = diaBR(new Date(agora));
  const ontem = diaBR(new Date(agora - DIA));
  const doDia = comFoto.filter((n) => diaBR(n.data) === hoje);
  const pool = doDia.length >= 5 ? doDia
    : comFoto.filter((n) => [hoje, ontem].includes(diaBR(n.data))).length >= 5
      ? comFoto.filter((n) => [hoje, ontem].includes(diaBR(n.data)))
      : comFoto.slice(0, 20);
  // Ordem dos destaques: por TIPO (drogas, armas, contrabando, veículos,
  // dinheiro, ambientais, medicamentos, patrimoniais, outras) e, dentro de cada
  // tipo, da maior apreensão para a menor. Desdobramentos (soltura, condenação,
  // incineração) vão para o fim.
  const destaques = [...pool].sort(ordemPorTipo);
  const manchete = destaques[0] || ns[0];
  const usados = new Set([manchete]);
  const lado = destaques.slice(1, 5);
  lado.forEach((n) => usados.add(n));

  // Fronteira: 2 principais (com foto) e até 6 menores, das últimas 24 h (amplia para 48 h e 7 dias
  // se houver poucas), sem repetir a manchete e os destaques. Ordem: importância com prazo de validade.
  const daFronteira = (h) => ns.filter((n) => n.polo && !usados.has(n) && n.data && horas(n) <= h && n.data.getTime() <= agora + 3600000);
  // Ordem pedida pelo responsável: Foz do Iguaçu, Guaíra, Toledo, Santa Helena, Medianeira, São Miguel
  // do Iguaçu, Itaipulândia, demais lindeiras de Itaipu e, por fim, as outras fronteiras. A região de
  // Foz e do Lago de Itaipu entra sempre que tiver notícia nas últimas 48 h.
  const janelaFr = [24, 48, 7 * 24].map(daFronteira).find((l) => l.length >= 4) || daFronteira(7 * 24);
  const itaipu48 = daFronteira(48).filter((n) => n.prioridadeFr <= 8 && !janelaFr.includes(n));
  // Primeiro o dia (hoje antes de ontem); dentro do dia, a ordem regional (Foz primeiro) e a relevância.
  const ordemFr = [...janelaFr, ...itaipu48].sort((a, b) => diaBR(b.data).localeCompare(diaBR(a.data)) ||
    (soPessoa(a) - soPessoa(b)) || a.prioridadeFr - b.prioridadeFr || nota(b) - nota(a) || b.data - a.data);
  // Destaque só com foto: a foto do próprio item ou a que o servidor busca no link original (sem link,
  // não há foto). Na ordem acima; sem nenhuma com foto, vale a ordem pura.
  const temFoto = (n) => Boolean(n.img || n.temLink);
  const frPrincipais = [...ordemFr.filter(temFoto), ...ordemFr.filter((n) => !temFoto(n))].slice(0, 2);
  // Menores: apreensão de adolescente sem material (moto roubada etc.) só entra se faltar notícia.
  const restoFr = ordemFr.filter((n) => !frPrincipais.includes(n));
  const frMenores = [...restoFr.filter((n) => !soPessoa(n)), ...restoFr.filter(soPessoa)].slice(0, 6).sort((a, b) => b.data - a.data);
  [...frPrincipais, ...frMenores].forEach((n) => usados.add(n));
  const lugarFr = (n) => `${n.cidade ? `${n.cidade} (${n.uf})` : (NOME_UF[n.uf] || '')}`;
  const blocoFronteira = frPrincipais.length ? `<section class="fronteira" aria-label="Fronteira">` +
    `<div class="section-head"><h2>Fronteira</h2><span class="count">Apreensões nas regiões de fronteira</span></div>` +
    `<div class="fr-principais">${frPrincipais.map((n) => `<a class="story" href="${urlNoticia(n)}" data-read="${n.i}">${midia(n)}` +
      `<div><div class="kicker">${esc(n.polo)}</div><h3 class="headline">${esc(n.titulo)}</h3>` +
      `${n.resumo ? `<p class="dek">${esc(curto(n.resumo, 160))}</p>` : ''}${metaHTML(n)}</div></a>`).join('')}</div>` +
    (frMenores.length ? `<ul class="fr-menores">${frMenores.map((n) => `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}">` +
      `<span class="fr-lugar">${esc(lugarFr(n))}</span><h4 class="headline">${esc(n.titulo)}</h4>${metaHTML(n)}</a></li>`).join('')}</ul>` : '') +
    `</section>` : '';

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
  // Editorias na mesma ordem dos tipos (drogas primeiro), as 4 primeiras com notícias.
  const editorias = [...porCat].sort((a, b) => a[0] - b[0]).slice(0, 4);

  $('inicio').innerHTML =
    `<section class="lead" aria-label="Destaques">` +
      `<div class="lead-main">${story(manchete, { dek: true, cont: true }).replace('<h3 class="headline">', '<h2 class="headline">').replace('</h3>', '</h2>')}</div>` +
      `<div class="lead-side">${lado.map((n) => `<a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><div>${kickerHTML(n, st.ctx)}<h3 class="headline">${esc(n.titulo)}</h3>${metaHTML(n)}</div>${midia(n)}</a>`).join('')}</div>` +
    `</section>` +
    blocoFronteira +
    `<div class="section-head"><h2>Em alta e em números</h2><a href="observatorio">Abrir o Observatório →</a></div>` +
    `<section class="band">` +
      `<div class="panel"><h3>Em alta</h3>${alta.length ? `<ol class="trend">${alta.map((n) =>
        `<li><a class="story" href="${urlNoticia(n)}" data-read="${n.i}"><h4 class="headline">${esc(n.titulo)}</h4><div class="meta"><span class="sources">${n.outras.length + 1} veículos</span> · ${esc(relativo(n.data))}</div></a></li>`).join('')}</ol>`
        : '<p class="note">Sem matérias repercutidas nas últimas 48 horas.</p>'}<p class="note">Matérias publicadas por mais veículos nas últimas 24 horas.</p></div>` +
      `<div class="panel"><h3>Últimos 30 dias</h3><dl class="kpis">` +
        `<div class="kpi"><dt>Notícias</dt><dd>${num(r30.length)}</dd></div>` +
        `<div class="kpi"><dt>Cocaína</dt><dd>≈ ${qtd(soma('coc'), 'kg')}</dd></div>` +
        `<div class="kpi"><dt>Maconha e skunk</dt><dd>≈ ${qtd(soma('mac') + soma('skh'), 'kg')}</dd></div>` +
        `<div class="kpi"><dt>Armas de fogo</dt><dd>≈ ${qtd(soma('arm'), 'un')}</dd></div>` +
      `</dl><p class="note">Valores estimados com base nas quantidades informadas pela imprensa. Apreensões sem peso divulgado não integram a soma. Dados de caráter informativo, sem valor de estatística oficial.</p></div>` +
      `<div class="panel"><h3>Notícias por estado · 30 dias</h3><div class="map" id="mapaInicio"></div></div>` +
    `</section>` +
    `<div class="editorias">${editorias.map(([c, itens]) => {
      // Cada matéria aparece em uma só editoria da página inicial.
      // Na editoria: sempre o mais recente. Janela = últimas 24 h (amplia para
      // 48 h, 72 h ou 7 dias só se o tipo tiver menos de 4 matérias). Abre com a
      // maior apreensão da janela (com foto); a lista ao lado vem por data.
      const porTamanho = (a, b) => (desdobramento(a) - desdobramento(b)) || (tamanhoNo(b, c) - tamanhoNo(a, c)) || (b.data - a.data);
      const porData = (a, b) => (desdobramento(a) - desdobramento(b)) || (b.data - a.data);
      const livresTodos = itens.filter((n) => !usados.has(n) && n.data && n.data.getTime() <= agora + 3600000);
      const janela = [24, 48, 72, 7 * 24].map((h) => livresTodos.filter((n) => horas(n) <= h)).find((l) => l.length >= 4)
        || [...livresTodos].sort((a, b) => b.data - a.data).slice(0, 8);
      const livres = [...janela].sort(porTamanho);
      const primeira = livres.find((n) => n.img) || livres[0] || itens[0];
      usados.add(primeira);
      const resto = janela.filter((n) => n !== primeira && !usados.has(n)).sort(porData).slice(0, 3);
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
  // Palavras curtas de ligação ("do", "de", "em") não filtram nada; cada termo precisa
  // ser começo de palavra; com 2+ termos, a frase inteira também é aceita.
  const LIGACAO = new Set(['a', 'o', 'as', 'os', 'e', 'de', 'da', 'do', 'das', 'dos', 'em', 'na', 'no', 'nas', 'nos']);
  const palavras = fold(q).replace(/[^a-z0-9]+/g, ' ').trim().split(' ').filter(Boolean);
  const termos = palavras.filter((t) => !LIGACAO.has(t) || palavras.length === 1).map((t) => ' ' + t);
  const c = cat === '' ? -1 : Number(cat);
  return st.ctx.noticias.filter((n) => (!uf || n.uf === uf) && (c < 0 || n.cats.includes(c)) &&
    (!ano || String(n.ano) === ano) && termos.every((t) => n.busca.includes(t)));
}
function render() {
  const f = st.filtro, filtrado = temFiltro();
  $('inicio').hidden = filtrado;
  $('agoraFaixa').hidden = filtrado;  // renderAgora respeita o mesmo filtro
  st.lista = filtrar();
  const partes = [f.cat !== '' ? st.ctx.categorias[f.cat] : '', f.uf ? NOME_UF[f.uf] : '', f.ano, f.q ? `“${f.q}”` : ''].filter(Boolean);
  $('resTitulo').textContent = filtrado ? partes.join(' · ') : 'Últimas notícias';
  $('contagem').innerHTML = `<b>${num(st.lista.length)}</b> ${st.lista.length === 1 ? 'notícia' : 'notícias'}`;
  $('lista').innerHTML = st.lista.length ? st.lista.slice(0, st.limite).map(linha).join('')
    : '<li class="empty">Nenhuma notícia encontrada. Tente outro termo ou remova um filtro.</li>';
  $('mais').hidden = st.limite >= st.lista.length;
  // Busca sem ano escolhido: procura nos últimos 6 meses e oferece o acervo inteiro.
  if (f.q && !f.ano && !st.tudo && st.ctx.recorte) {
    $('lista').insertAdjacentHTML('beforeend', `<li class="empty busca-tudo">Resultados dos últimos 6 meses. ` +
      `<button type="button" class="btn ghost" id="buscarTudo">Buscar em todo o acervo (desde 2006)</button></li>`);
    $('buscarTudo').addEventListener('click', (e) => buscarTudo(e.currentTarget));
  }
  $('limpar').hidden = !filtrado;
  $('fEstado').value = f.uf; $('fCategoria').value = f.cat; $('fAno').value = f.ano;
  if ($('buscaTopo').value.trim() !== f.q) $('buscaTopo').value = f.q;  // não apaga o espaço que a pessoa acabou de digitar
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
  // Anos do acervo inteiro (anos/indice.json); os anteriores aos 6 meses do feed carregam ao escolher.
  indiceAnos().then((ind) => {
    const anos = [...new Set([...Object.keys(ind?.anos || {}).map(Number), ...st.ctx.noticias.map((n) => n.ano)])]
      .filter((a) => a >= 2006).sort((a, b) => b - a);
    $('fAno').insertAdjacentHTML('beforeend', anos.map((a) => `<option value="${a}">${a}</option>`).join(''));
    $('fAno').value = st.filtro.ano;
  });

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
  // 1º os últimos 31 dias (abre rápido e já monta manchete, destaques e panorama);
  // depois o acervo completo, para a lista com busca e filtros por ano.
  const rapida = carregarFeed('feed-recente.json').catch(() => null);
  const promessa = carregarFeed();
  iniciarCabecalho(promessa);
  $('lista').innerHTML = '<li><div class="sk" style="height:120px;margin:18px 0"></div></li>'.repeat(4);
  rapida.then((ctx) => {
    if (!ctx || st.ctx) return;
    const filtro = lerHash();
    if (!filtro.q && !filtro.uf && !filtro.cat && !filtro.ano) { st.ctx = ctx; renderInicio(); st.ctx = null; }
  });
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
  if (st.filtro.ano) garantirAno().then(render);
  iniciarLeitor(st.ctx);
  setInterval(atualizarAoVivo, 5 * 60000);
  setInterval(conferirAgora, 60000);  // notícia nova aparece na faixa Agora em até 1 minuto
  document.addEventListener('visibilitychange', () => { if (!document.hidden) conferirAgora(); });
}
iniciar();
