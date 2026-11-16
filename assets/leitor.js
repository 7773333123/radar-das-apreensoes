/* Leitor de notícias (janela), galeria de fotos e visualizador em tela cheia. */
import { $, esc, num, dataBR, urlSegura, debounce, imgTag, placeholder, NOME_UF } from './core.js';

const HTML = `
<dialog class="reader" id="leitor" aria-labelledby="leitorTitulo">
  <div class="reader-bar"><span class="brand-name">Radar das Apreensões</span>
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
  const lote = Math.floor(i / 100);
  if (!detalhesCache.has(lote)) detalhesCache.set(lote, fetch(`det/${lote}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({})));
  return detalhesCache.get(lote).then((d) => d[String(i)] || {});
};
let linksPromise = null;
const carregarLinks = () => (linksPromise ??= fetch('feed_links.json').then((r) => (r.ok ? r.json() : [])).catch(() => []));

export function kickerHTML(n, ctx, preferida = null) {
  const c = preferida != null && n.cats.includes(Number(preferida)) ? Number(preferida) : n.cats[0];
  const cat = c != null ? ctx.categorias[c] : 'Apreensões';
  return `<div class="kicker">${esc(cat)}${n.uf ? ` <span class="uf">· ${esc(NOME_UF[n.uf])}</span>` : ''}` +
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
  function fichaHTML(n, t) {
    const f = (t && t.f) || {};
    const linhas = [
      ['Apreendido', (f.apreendido || []).join(', ')],
      ['Onde', [(f.cidades || []).join(', ') || (n.uf ? NOME_UF[n.uf] : ''), f.rodovia ? `rodovia ${f.rodovia}` : ''].filter(Boolean).join(' · ')],
      ['Quem atuou', (f.orgaos || []).join(', ')],
      ['Presos', f.presos ? `${num(f.presos)} ${f.presos === 1 ? 'pessoa' : 'pessoas'}` : (f.presos_texto ? 'Sim, segundo a reportagem' : '')],
      ['Mandados', f.mandados || ''], ['Operação', f.operacao || ''], ['Valores citados', f.valor || ''],
      ['Publicado em', dataBR(n.data)],
      ['Fonte', n.fonte + (n.outras.length ? ` (também em ${n.outras.map((o) => o[0]).join(', ')})` : '')],
    ].filter(([, v]) => v);
    return (t && t.s ? `<h2>Resumo do Radar</h2>${paragrafos(t.s)}` : '') +
      `<section class="facts"><h2>Principais informações</h2><dl>${linhas.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl></section>` +
      '<p class="reader-note">Resumo e ficha elaborados automaticamente pelo Radar a partir dos fatos publicados. A reportagem completa está no site de origem.</p>';
  }

  function paragrafos(texto) {
    return String(texto).split(/\n{2,}/).filter((p) => p.trim()).map((p) => `<p class="reader-text">${esc(p.trim())}</p>`).join('');
  }

  function fonteHTML(n, t) {
    if (Array.isArray(t?.p)) {
      return `<h2>Texto completo</h2>${t.p.map((p) => `<p class="reader-text">${esc(p)}</p>`).join('')}` +
        `<p class="reader-note">Texto reproduzido integralmente de ${esc(n.fonte)}, sob a licença ${esc(t.l)}, que permite a reprodução com crédito.</p>`;
    }
    const trecho = t?.tr && t.tr.length > (n.resumo || '').length ? t.tr : n.resumo;
    if (!trecho) return '';
    return `<h2>O que diz a fonte</h2><blockquote class="reader-quote">${paragrafos(trecho)}</blockquote>` +
      `<p class="reader-note">${t?.tr ? 'Abertura da reportagem publicada' : 'Resumo publicado'} por ${esc(n.fonte)}, reproduzido com crédito. ` +
      `A reportagem continua no site de origem: <a href="${esc(n.url || '#')}" target="_blank" rel="noopener noreferrer" data-ler-original>ler a íntegra ↗</a></p>`;
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
      const link = `${location.origin}/#noticia-${n.i}`;
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
