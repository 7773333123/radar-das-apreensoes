/* Leitor de notícias (janela), galeria de fotos e visualizador em tela cheia. */
import { $, esc, num, dataBR, urlSegura, debounce, imgTag, placeholder, NOME_UF, urlNoticia } from './core.js';

const HTML = `
<dialog class="reader" id="leitor" aria-labelledby="leitorTitulo">
  <div class="reader-bar"><span class="brand"><svg class="brand-mark" viewBox="0 0 64 64" aria-hidden="true"><path d="M32 3C19 3 9 13 9 26c0 17 23 35.5 23 35.5S55 43 55 26C55 13 45 3 32 3z" fill="#b3261e"/><path d="M24.5 40V14.5h9a8 8 0 0 1 0 16h-9" fill="none" stroke="#fff" stroke-width="5.4" stroke-linejoin="round"/><path d="M31.5 30.5l9.5 9.5" stroke="#fff" stroke-width="5.4" stroke-linecap="round"/><path d="M40.5 9.6a11 11 0 0 1 7.9 7.9" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".55"/><path d="M40.6 13.8a6.6 6.6 0 0 1 3.6 3.6" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" opacity=".9"/></svg><span class="brand-name"><b>RADAR</b><span>das Apreensões</span></span></span>
    <button type="button" class="reader-close" id="fecharLeitor">Fechar ✕</button></div>
  <article class="reader-body" id="leitorConteudo"></article>
</dialog>
<dialog class="viewer" id="visor" aria-label="Fotos da reportagem">
  <div class="viewer-bar"><span id="visorContador"></span>
    <a id="visorOriginal" href="#" target="_blank" rel="noopener noreferrer">Abrir imagem ↗</a>
    <button type="button" id="fecharVisor" aria-label="Fechar fotos">✕</button></div>
  <div class="viewer-stage">
    <button type="button" class="gal-nav prev" data-visor="-1" aria-label="Foto anterior">‹</button>
    <img id="visorImg" alt="" referrerpolicy="no-referrer">
    <button type="button" class="gal-nav next" data-visor="1" aria-label="Próxima foto">›</button>
  </div>
  <p class="viewer-credit" id="visorCredito"></p>
</dialog>`;

const detalhesCache = new Map();
const carregarDetalhe = (i) => {
  const lote = Number(i) % 256; // mesmo LOTES de gerar_feed_site.py
  if (!detalhesCache.has(lote)) detalhesCache.set(lote, fetch(`/det/${lote}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({})));
  return detalhesCache.get(lote).then((d) => d[String(i)] || {});
};
let linksPromise = null;
const carregarLinks = () => (linksPromise ??= fetch('/feed_links.json').then((r) => (r.ok ? r.json() : {})).catch(() => ({})));

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

export function kickerHTML(n, ctx, preferida = null) {
  const c = preferida != null && n.cats.includes(Number(preferida)) ? Number(preferida) : n.cats[0];
  const cat = c != null ? ctx.categorias[c] : 'Apreensões';
  const lugar = n.cidade ? `${n.cidade} (${n.uf})` : NOME_UF[n.uf];
  return `<div class="kicker">${esc(cat)}${n.uf ? ` <span class="uf">· ${esc(lugar)}</span>` : ''}` +
    `${n.texto ? ' <span class="badge">· Texto completo</span>' : ''}</div>`;
}
export function metaHTML(n) {
  const fontes = n.outras.length ? ` · <span class="sources">+${n.outras.length} ${n.outras.length === 1 ? 'fonte' : 'fontes'}</span>` : '';
  return `<div class="meta">${esc(dataBR(n.data))} · ${esc(n.fonte)}${fontes}</div>`;
}

export function iniciarLeitor(ctx, { aoFechar } = {}) {
  document.body.insertAdjacentHTML('beforeend', HTML);
  const galeria = { fotos: [], atual: 0, fonte: '' };

  function irPara(k, suave = true) {
    const t = $('galTrilho');
    if (t?.children[k]) t.scrollTo({ left: t.children[k].offsetLeft, behavior: suave ? 'smooth' : 'auto' });
  }
  function abrirVisor(k) {
    galeria.atual = (k + galeria.fotos.length) % galeria.fotos.length;
    const src = galeria.fotos[galeria.atual];
    Object.assign($('visorImg'), { src, alt: `Foto ${galeria.atual + 1} de ${galeria.fotos.length}` });
    $('visorContador').textContent = `${galeria.atual + 1} / ${galeria.fotos.length}`;
    $('visorCredito').textContent = `Imagem: ${galeria.fonte}`;
    $('visorOriginal').href = src;
    document.querySelectorAll('#visor .gal-nav').forEach((b) => { b.hidden = galeria.fotos.length < 2; });
    if (!$('visor').open) $('visor').showModal();
    irPara(galeria.atual, false);
  }
  function montarGaleria(n, fotos) {
    Object.assign(galeria, { fotos, fonte: n.fonte, atual: 0 });
    const alvo = $('leitorFotos');
    if (!alvo) return;
    if (!fotos.length) {
      alvo.innerHTML = `<div class="media">${placeholder(n)}</div>`;
      $('leitorMiniaturas').innerHTML = '';
      return;
    }
    alvo.innerHTML = `<div class="gallery"><div class="gallery-track" id="galTrilho" tabindex="0" aria-label="Fotos da reportagem">` +
      fotos.map((src, k) => `<figure class="slide"><button type="button" class="slide-btn" data-foto="${k}" aria-label="Ampliar foto ${k + 1}">${imgTag(src, `Foto ${k + 1} da reportagem`)}</button></figure>`).join('') +
      `</div>${fotos.length > 1 ? `<button type="button" class="gal-nav prev" data-gal="-1" aria-label="Foto anterior">‹</button><button type="button" class="gal-nav next" data-gal="1" aria-label="Próxima foto">›</button><span class="gal-count" id="galContador">1 / ${fotos.length}</span>` : ''}</div>` +
      `<p class="reader-credit">${fotos.length > 1 ? `${fotos.length} fotos · ` : ''}Imagens: ${esc(n.fonte)}. Direitos reservados à fonte.</p>`;
    $('leitorMiniaturas').innerHTML = fotos.length < 2 ? '' :
      `<h2>Fotos da reportagem (${fotos.length})</h2><div class="thumbs-grid">` +
      fotos.map((src, k) => `<button type="button" class="thumb-btn" data-foto="${k}" aria-label="Ver foto ${k + 1}">${imgTag(src)}</button>`).join('') + '</div>';
    const t = $('galTrilho');
    t.addEventListener('scroll', debounce(() => {
      galeria.atual = Math.min(fotos.length - 1, Math.max(0, Math.round(t.scrollLeft / Math.max(1, t.clientWidth))));
      if ($('galContador')) $('galContador').textContent = `${galeria.atual + 1} / ${fotos.length}`;
    }, 60));
  }
  // Ficha "Em resumo", Resumo do Radar em seções e a fonte em cartão próprio.
  // (A página própria da notícia, api/pagina.js, segue a mesma estrutura.)
  function fichaHTML(n, t) {
    const f = (t && t.f) || {};
    const linhas = [
      ['Apreendido', (f.apreendido || []).join(', ')],
      ['Onde', [(f.cidades || []).join(', ') || (n.uf ? NOME_UF[n.uf] : ''), f.rodovia ? `rodovia ${f.rodovia}` : ''].filter(Boolean).join(' · ')],
      ['Quem atuou', (f.orgaos || []).join(', ')],
      ['Presos', (f.presos_iniciais && f.presos_iniciais.length ? f.presos_iniciais.join(', ') + (f.presos > f.presos_iniciais.length ? ` (${num(f.presos)} no total)` : '')
      : f.presos ? `${num(f.presos)} ${f.presos === 1 ? 'pessoa' : 'pessoas'}` : (f.presos_texto ? 'Sim, segundo a reportagem' : ''))],
      ['Como', (f.como || []).join(', ')],
      ['Onde estava', [(f.esconderijo || []).join(', '), f.veiculo || ''].filter(Boolean).join(' · ')],
      ['Crimes citados', (f.crimes || []).join(', ')],
      ['Mandados', f.mandados || ''], ['Operação', f.operacao || ''], ['Valores citados', f.valor || ''],
      ['Publicado em', dataBR(n.data)],
    ].filter(([, v]) => v);
    const secoes = Array.isArray(t?.sx) && t.sx.length ? t.sx
      : (t?.s ? String(t.s).split(/\n{2,}/).filter(Boolean).map((p) => ['', p]) : []);
    return `<section class="em-resumo" aria-label="Em resumo"><h2>Em resumo</h2><dl>${linhas.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></section>` +
      radarHTML(secoes, [n.fonte, ...n.outras.map((o) => o[0])].filter(Boolean));
  }

  function paragrafos(texto) {
    return String(texto).split(/\n{2,}/).filter((p) => p.trim()).map((p) => `<p class="reader-text">${esc(p.trim())}</p>`).join('');
  }

  function fonteHTML(n, t) {
    const link = `<a class="btn" href="${esc(n.url || '#')}" target="_blank" rel="noopener noreferrer" data-ler-original>Ler a reportagem completa em ${esc(n.fonte)} ↗</a>`;
    const cab = (titulo) => `<header class="bloco-cab"><h2>${titulo}</h2><p><strong>${esc(n.fonte)}</strong> · ${esc(dataBR(n.data))}</p></header>`;
    if (Array.isArray(t?.p)) {
      return `<section class="bloco fonte-card">${cab('Texto completo')}<div class="fonte-texto">${textoOriginalHTML(t.p)}</div>` +
        `<footer class="fonte-pe"><span>${t.l === 'oficial' ? `Comunicado oficial de ${esc(n.fonte)}, reproduzido na íntegra com crédito.`
          : `Reproduzido de ${esc(n.fonte)} sob a licença ${esc(t.l)}, que permite a reprodução com crédito.`}</span>${link}</footer></section>`;
    }
    const trecho = t?.tr && t.tr.length > (n.resumo || '').length ? t.tr : n.resumo;
    if (!trecho) return n.url ? `<section class="bloco fonte-card">${cab('O que diz a fonte')}<footer class="fonte-pe"><span>A reportagem está disponível no site de origem.</span>${link}</footer></section>` : '';
    const pct = t?.tr && t?.tt ? Math.min(50, Math.max(1, Math.round((t.tr.length / t.tt) * 100))) : 0;
    return `<section class="bloco fonte-card">${cab('O que diz a fonte')}<blockquote class="reader-quote">${paragrafos(trecho)}</blockquote>` +
      `<footer class="fonte-pe"><span>${t?.tr ? `Abertura da reportagem${pct ? `, cerca de ${pct}% do texto original` : ''}, reproduzida com crédito.` : 'Resumo publicado pelo veículo, reproduzido com crédito.'}</span>${link}</footer></section>`;
  }

  function abrir(i, { atualizarUrl = true } = {}) {
    const n = ctx.porIndice.get(Number(i));
    if (!n) return;
    const cats = n.cats.map((c) => ctx.categorias[c]).join(' · ') || 'Em classificação';
    const fonte = `<div id="leitorTexto">${n.texto ? '<p class="reader-note">Carregando o texto…</p>' : fonteHTML(n, null)}</div>`;
    const c = $('leitorConteudo');
    c.innerHTML = `${kickerHTML(n, ctx)}<h1 id="leitorTitulo">${esc(n.titulo)}</h1>${metaHTML(n)}` +
      `<div id="leitorFotos" class="reader-media"></div><div id="leitorRadar"><p class="reader-note">Carregando o resumo…</p></div>${fonte}<div id="leitorMiniaturas"></div>` +
      `<footer class="reader-foot"><span>Fonte: ${esc(n.fonte)}${n.uf ? ' · ' + esc(NOME_UF[n.uf]) : ''} · ${esc(cats)}</span>` +
      `<span class="links"><a class="link-sm" id="leitorLink" href="${esc(n.url || '#')}" target="_blank" rel="noopener noreferrer"${n.url ? '' : ' aria-disabled="true"'}>ver original ↗</a>` +
      `<button type="button" class="link-sm" id="compartilhar">compartilhar</button></span>` +
      (n.outras.length ? `<span class="also">também em: ${n.outras.map(([f, url, k]) => `<a class="link-sm" href="${esc(urlSegura(url || '') || '#')}" target="_blank" rel="noopener noreferrer" data-outra="${Number(k)}">${esc(f)}</a>`).join(', ')}</span>` : '') +
      '</footer>';
    c.dataset.i = String(n.i);
    montarGaleria(n, n.img ? [n.img] : []);
    carregarDetalhe(n.i).then((t) => {
      if (c.dataset.i !== String(n.i)) return;
      if (Array.isArray(t.g) && t.g.length > 1) montarGaleria(n, t.g.map(urlSegura).filter(Boolean));
      $('leitorRadar').innerHTML = fichaHTML(n, t);
      $('leitorTexto').innerHTML = fonteHTML(n, t);
      const ler = c.querySelector('[data-ler-original]');
      if (ler && n.url) ler.href = n.url;
    });
    const semLink = [...c.querySelectorAll('[data-outra]')].filter((a) => a.getAttribute('href') === '#');
    if (semLink.length || !n.url) {
      carregarLinks().then((links) => {
        semLink.forEach((a) => { const u = urlSegura(links[a.dataset.outra] || ''); if (u) a.href = u; else a.replaceWith(a.textContent); });
        if (!n.url && c.dataset.i === String(n.i)) {
          const u = urlSegura(links[n.i] || '');
          if (u) {
            n.url = u; $('leitorLink').href = u; $('leitorLink').removeAttribute('aria-disabled');
            c.querySelectorAll('[data-ler-original]').forEach((a) => { a.href = u; });
          }
        }
      });
    }
    $('leitorLink').addEventListener('click', (e) => { if (e.currentTarget.getAttribute('aria-disabled') === 'true') e.preventDefault(); });
    $('compartilhar').addEventListener('click', async () => {
      const link = `${location.origin}${urlNoticia(n)}`;
      try {
        if (navigator.share) await navigator.share({ title: n.titulo, url: link });
        else { await navigator.clipboard.writeText(link); $('compartilhar').textContent = 'link copiado ✓'; }
      } catch { /* cancelado */ }
    });
    if (!$('leitor').open) $('leitor').showModal();
    $('leitor').scrollTop = 0;
    if (atualizarUrl) history.pushState({ leitor: n.i }, '', `#noticia-${n.i}`);
  }

  document.addEventListener('click', (e) => {
    const a = e.target.closest('[data-read]');
    if (a) { e.preventDefault(); abrir(a.dataset.read); }
  });
  $('leitor').addEventListener('click', (e) => {
    if (e.target === $('leitor')) return $('leitor').close();
    const nav = e.target.closest('[data-gal]');
    if (nav) return irPara(Math.min(galeria.fotos.length - 1, Math.max(0, galeria.atual + Number(nav.dataset.gal))));
    const f = e.target.closest('[data-foto]');
    if (f) abrirVisor(Number(f.dataset.foto));
  });
  $('fecharLeitor').addEventListener('click', () => $('leitor').close());
  $('leitor').addEventListener('close', () => {
    if (history.state && history.state.leitor != null) history.back();
    else if (location.hash.startsWith('#noticia-')) history.replaceState(null, '', location.pathname + location.search);
    aoFechar?.();
  });
  $('visor').addEventListener('click', (e) => {
    const nav = e.target.closest('[data-visor]');
    if (nav) return abrirVisor(galeria.atual + Number(nav.dataset.visor));
    if (e.target === $('visor') || e.target.closest('#fecharVisor')) $('visor').close();
  });
  $('visor').addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') abrirVisor(galeria.atual + 1);
    if (e.key === 'ArrowLeft') abrirVisor(galeria.atual - 1);
  });
  let x0 = null;
  $('visor').addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  $('visor').addEventListener('touchend', (e) => {
    if (x0 == null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) abrirVisor(galeria.atual + (dx < 0 ? 1 : -1));
    x0 = null;
  });
  const deHash = () => location.hash.match(/^#noticia-(\d+)$/)?.[1];
  window.addEventListener('popstate', () => {
    const i = deHash();
    if (i != null) abrir(i, { atualizarUrl: false });
    else if ($('leitor').open) $('leitor').close();
  });
  const inicial = deHash();
  if (inicial != null) abrir(inicial, { atualizarUrl: false });
  return abrir;
}
