/* Radar das Apreensões — lógica do site.
   Dados: feed.json (gerado por gerar_feed_site.py) e, sob demanda, feed_links.json. */
'use strict';
(() => {
  const $ = (id) => document.getElementById(id);
  const ESTADOS = [
    ['AC', 'Acre'], ['AL', 'Alagoas'], ['AP', 'Amapá'], ['AM', 'Amazonas'], ['BA', 'Bahia'], ['CE', 'Ceará'],
    ['DF', 'Distrito Federal'], ['ES', 'Espírito Santo'], ['GO', 'Goiás'], ['MA', 'Maranhão'], ['MT', 'Mato Grosso'],
    ['MS', 'Mato Grosso do Sul'], ['MG', 'Minas Gerais'], ['PA', 'Pará'], ['PB', 'Paraíba'], ['PR', 'Paraná'],
    ['PE', 'Pernambuco'], ['PI', 'Piauí'], ['RJ', 'Rio de Janeiro'], ['RN', 'Rio Grande do Norte'],
    ['RS', 'Rio Grande do Sul'], ['RO', 'Rondônia'], ['RR', 'Roraima'], ['SC', 'Santa Catarina'], ['SP', 'São Paulo'],
    ['SE', 'Sergipe'], ['TO', 'Tocantins'],
  ];
  const NOME_UF = Object.fromEntries(ESTADOS);
  // Posição aproximada de cada estado numa grade 7 × 7 (mapa em mosaico).
  const MOSAICO = {
    RR: [2, 0], AP: [4, 0],
    AM: [1, 1], PA: [3, 1], MA: [4, 1], CE: [5, 1], RN: [6, 1],
    AC: [0, 2], RO: [1, 2], MT: [2, 2], TO: [3, 2], PI: [4, 2], PE: [5, 2], PB: [6, 2],
    MS: [2, 3], GO: [3, 3], DF: [4, 3], BA: [5, 3], AL: [6, 3],
    PR: [2, 4], SP: [3, 4], MG: [4, 4], ES: [5, 4], SE: [6, 4],
    SC: [2, 5], RJ: [4, 5],
    RS: [2, 6],
  };
  const IMG_CATEGORIA = ['drogas-e-entorpecentes', 'armas-e-municoes', 'contrabando-e-descaminho', 'veiculos',
    'dinheiro-e-valores', 'crimes-ambientais', 'medicamentos-e-produtos', 'operacoes-patrimoniais', 'outras-apreensoes'];
  const POR_PAGINA = 30;
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  const state = { noticias: [], porIndice: new Map(), categorias: [], filtradas: [], limite: POR_PAGINA,
    filtro: { q: '', uf: '', cat: '', ano: '' } };

  // ---------- utilidades ----------
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const fold = (v) => String(v ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const urlSegura = (v) => { try { const u = new URL(v); return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : ''; } catch { return ''; } };
  const num = (n) => Number(n).toLocaleString('pt-BR');
  const dataBR = (d) => d ? d.toLocaleDateString('pt-BR', { timeZone: 'UTC', day: '2-digit', month: 'short', year: 'numeric' }).replace(/\./g, '') : 'Data não informada';
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  function preparar(raw, categorias) {
    const d = raw.d ? new Date(raw.d.length === 16 ? raw.d + 'Z' : raw.d) : null;
    const data = d && Number.isFinite(d.getTime()) ? d : null;
    const cats = (raw.c || []).filter((c) => categorias[c]);
    const uf = NOME_UF[raw.uf] ? raw.uf : '';
    const n = {
      i: raw.i, titulo: raw.t, fonte: raw.f || 'Fonte não informada', resumo: raw.r || '',
      url: urlSegura(raw.u || ''), img: urlSegura(raw.img || ''), uf, cats, data, texto: raw.x === 1, nFotos: raw.g || (raw.img ? 1 : 0),
      ano: data ? data.getUTCFullYear() : null,
    };
    n.busca = fold([n.titulo, n.resumo, n.fonte, uf, NOME_UF[uf], cats.map((c) => categorias[c]).join(' ')].join(' '));
    return n;
  }

  // ---------- filtros e estado na URL ----------
  function lerHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const legado = location.hash.match(/^#estado-(.+)$/); // links antigos: #estado-Bahia
    let uf = (p.get('uf') || '').toUpperCase();
    if (legado) { const v = decodeURIComponent(legado[1]); uf = NOME_UF[v.toUpperCase()] ? v.toUpperCase() : (ESTADOS.find(([, n]) => n === v) || [''])[0]; }
    const cat = p.get('cat') ?? '';
    return {
      q: p.get('q') || '', uf: NOME_UF[uf] ? uf : '',
      cat: /^\d+$/.test(cat) && state.categorias[cat] ? cat : '',
      ano: /^\d{4}$/.test(p.get('ano') || '') ? p.get('ano') : '',
      noticia: location.hash.match(/^#noticia-(\d+)$/)?.[1] ?? p.get('noticia'),
    };
  }
  function escreverHash() {
    const p = new URLSearchParams();
    for (const k of ['q', 'uf', 'cat', 'ano']) if (state.filtro[k]) p.set(k, state.filtro[k]);
    const h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }

  function aplicar({ rolar = false, resetar = true } = {}) {
    const { q, uf, cat, ano } = state.filtro;
    const termos = fold(q).split(/\s+/).filter(Boolean);
    const c = cat === '' ? -1 : Number(cat);
    state.filtradas = state.noticias.filter((n) =>
      (!uf || n.uf === uf) && (c < 0 || n.cats.includes(c)) && (!ano || String(n.ano) === ano) &&
      termos.every((t) => n.busca.includes(t)));
    if (resetar) state.limite = POR_PAGINA;
    sincronizarControles();
    renderLista();
    escreverHash();
    if (rolar) $('noticias').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }
  function definir(parcial, opts) { Object.assign(state.filtro, parcial); aplicar(opts); }

  function sincronizarControles() {
    const f = state.filtro;
    if ($('busca').value !== f.q) $('busca').value = f.q;
    $('fEstado').value = f.uf; $('fCategoria').value = f.cat; $('fAno').value = f.ano;
    for (const [id, v] of [['fEstado', f.uf], ['fCategoria', f.cat], ['fAno', f.ano]]) $(id).classList.toggle('active', !!v);
    document.querySelectorAll('.cat').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.cat === f.cat)));
    document.querySelectorAll('.tile').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.uf === f.uf)));
    document.querySelectorAll('.bar').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.cat === f.cat)));
  }

  // ---------- renderização ----------
  function tagsHTML(n) {
    const cats = n.cats.slice(0, 2).map((c) => `<span class="tag">${esc(state.categorias[c])}</span>`).join('') +
      (n.texto ? '<span class="tag full">Texto completo</span>' : '') +
      (n.nFotos > 1 ? `<span class="tag photos">${n.nFotos} fotos</span>` : '');
    const uf = n.uf ? `<span class="tag uf">${esc(NOME_UF[n.uf])}</span>` : '<span class="tag muted">Estado não identificado</span>';
    return `<div class="tags">${cats || '<span class="tag muted">Em classificação</span>'}${uf}</div>`;
  }
  const metaHTML = (n) => `<div class="meta">${esc(dataBR(n.data))} · ${esc(n.fonte)}</div>`;
  const imgHTML = (src, alt, extra = '') => `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" ${extra}>`;

  function cardHTML(n) {
    const media = n.img ? imgHTML(n.img, '', `data-fallback="${ilustracao(n)}"`) : imgHTML(ilustracao(n), '');
    return `<button type="button" class="card" data-read="${n.i}"><div class="card-media">${media}</div>` +
      `<div class="card-body">${tagsHTML(n)}<h3>${esc(n.titulo)}</h3>${metaHTML(n)}</div></button>`;
  }
  function itemHTML(n) {
    const thumb = n.img ? `<div class="thumb">${imgHTML(n.img, '', `data-fallback="${ilustracao(n)}"`)}</div>`
      : `<div class="thumb ilustr">${imgHTML(ilustracao(n), '')}</div>`;
    return `<li class="item"><button type="button" class="item-btn" data-read="${n.i}"><div>${tagsHTML(n)}` +
      `<h3>${esc(n.titulo)}</h3>${n.resumo ? `<p>${esc(n.resumo)}</p>` : ''}${metaHTML(n)}</div>${thumb}</button></li>`;
  }

  function renderLista() {
    const lista = state.filtradas;
    const total = lista.length;
    const f = state.filtro;
    const partes = [];
    if (f.uf) partes.push(NOME_UF[f.uf]);
    if (f.cat !== '') partes.push(state.categorias[f.cat]);
    if (f.ano) partes.push(f.ano);
    if (f.q) partes.push(`“${f.q}”`);
    $('not-titulo').textContent = partes.length ? 'Resultados' : 'Últimas notícias';
    $('contagem').innerHTML = `<b>${num(total)}</b> ${total === 1 ? 'notícia' : 'notícias'}${partes.length ? ' · ' + esc(partes.join(' · ')) : ''}`;

    // Destaques: as mais recentes, preferindo as que têm foto.
    const recentes = lista.slice(0, 40);
    const destaques = [...recentes.filter((n) => n.img), ...recentes.filter((n) => !n.img)].slice(0, 3);
    const usados = new Set(destaques);
    const resto = lista.filter((n) => !usados.has(n));
    $('destaques').innerHTML = destaques.map(cardHTML).join('');
    $('lista').innerHTML = resto.slice(0, Math.max(0, state.limite - destaques.length)).map(itemHTML).join('');
    $('mais').hidden = state.limite >= total;
    const msg = $('mensagem');
    msg.hidden = total > 0;
    if (!total) msg.innerHTML = '<strong>Nenhuma notícia encontrada</strong>Tente outro termo ou remova algum filtro.<br><button type="button" class="btn" data-limpar>Limpar filtros</button>';
  }

  function renderPainel() {
    const porUf = new Map(), porCat = new Map(), porMes = new Map(), fontes = new Set();
    const agora = Date.now(), corte = agora - 30 * 86400000;
    let recentes = 0;
    for (const n of state.noticias) {
      if (n.uf) porUf.set(n.uf, (porUf.get(n.uf) || 0) + 1);
      for (const c of n.cats) porCat.set(c, (porCat.get(c) || 0) + 1);
      if (n.fonte !== 'Fonte não informada') fontes.add(n.fonte);
      if (n.data) {
        const t = n.data.getTime();
        if (t >= corte && t <= agora) recentes++;
        const k = n.data.toISOString().slice(0, 7);
        porMes.set(k, (porMes.get(k) || 0) + 1);
      }
    }
    $('kTotal').textContent = num(state.noticias.length);
    $('kRecentes').textContent = num(recentes);
    $('kEstados').textContent = num(porUf.size);
    $('kFontes').textContent = num(fontes.size);

    const maxUf = Math.max(1, ...porUf.values());
    $('mapa').innerHTML = Object.entries(MOSAICO).map(([uf, [x, y]]) => {
      const v = porUf.get(uf) || 0;
      const a = 0.08 + 0.92 * Math.sqrt(v / maxUf);
      return `<button type="button" class="tile${a > 0.55 ? ' hot' : ''}" data-uf="${uf}" style="grid-column:${x + 1};grid-row:${y + 1};--a:${a.toFixed(2)}" ` +
        `title="${esc(NOME_UF[uf])}: ${num(v)} notícias" aria-label="${esc(NOME_UF[uf])}, ${num(v)} notícias">${uf}<small>${num(v)}</small></button>`;
    }).join('');

    const cats = [...porCat].sort((a, b) => b[1] - a[1]);
    const maxCat = Math.max(1, ...porCat.values());
    $('barCategorias').innerHTML = cats.map(([c, v]) =>
      `<button type="button" class="bar" data-cat="${c}"><span>${esc(state.categorias[c])}</span><span class="val">${num(v)}</span>` +
      `<span class="track"><span class="fill" style="width:${Math.max(2, 100 * v / maxCat)}%"></span></span></button>`).join('');

    const hoje = new Date();
    const meses = [];
    for (let k = 11; k >= 0; k--) {
      const d = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth() - k, 1));
      const chave = d.toISOString().slice(0, 7);
      meses.push([chave, MESES[d.getUTCMonth()], porMes.get(chave) || 0]);
    }
    const maxMes = Math.max(1, ...meses.map((m) => m[2]));
    $('meses').innerHTML = meses.map(([chave, rot, v]) =>
      `<div class="month" title="${rot}/${chave.slice(0, 4)}: ${num(v)} notícias"><span style="height:${(100 * v / maxMes).toFixed(1)}%"></span><small>${rot}</small></div>`).join('');
  }

  function preencherSelects() {
    $('fEstado').insertAdjacentHTML('beforeend', ESTADOS.map(([uf, nome]) => `<option value="${uf}">${esc(nome)}</option>`).join(''));
    $('fCategoria').insertAdjacentHTML('beforeend', state.categorias.map((c, k) => `<option value="${k}">${esc(c)}</option>`).join(''));
    const anos = [...new Set(state.noticias.map((n) => n.ano).filter(Boolean))].sort((a, b) => b - a);
    $('fAno').insertAdjacentHTML('beforeend', anos.map((a) => `<option value="${a}">${a}</option>`).join(''));
  }

  // ---------- leitor ----------
  const detalhesCache = new Map();
  const carregarDetalhe = (i) => {
    const lote = Math.floor(i / 1000);
    if (!detalhesCache.has(lote)) detalhesCache.set(lote, fetch(`detalhes/${lote}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({})));
    return detalhesCache.get(lote).then((d) => d[String(i)] || {});
  };
  const ilustracao = (n) => `img/categorias/${IMG_CATEGORIA[n.cats[0] ?? 8]}.webp`;

  // ---------- galeria ----------
  const galeria = { fotos: [], atual: 0, fonte: '' };
  function galeriaHTML(fotos, fonte) {
    const slides = fotos.map((src, k) => `<figure class="slide"><button type="button" class="slide-btn" data-foto="${k}" aria-label="Ampliar foto ${k + 1} de ${fotos.length}">` +
      `${imgHTML(src, `Foto ${k + 1} da reportagem`, k ? '' : 'fetchpriority="high"')}</button></figure>`).join('');
    const nav = fotos.length > 1
      ? `<button type="button" class="gal-nav prev" data-gal="-1" aria-label="Foto anterior">‹</button><button type="button" class="gal-nav next" data-gal="1" aria-label="Próxima foto">›</button><span class="gal-count" id="galContador">1 / ${fotos.length}</span>`
      : '';
    return `<div class="gallery"><div class="gallery-track" id="galTrilho" tabindex="0" aria-label="Fotos da reportagem">${slides}</div>${nav}</div>` +
      `<p class="reader-credit">${fotos.length > 1 ? `${fotos.length} fotos · ` : ''}Imagens: ${esc(fonte)}. Direitos reservados à fonte.</p>`;
  }
  function miniaturasHTML(fotos) {
    if (fotos.length < 2) return '';
    return `<section class="thumbs" aria-label="Todas as fotos"><h2>Fotos da reportagem <span>(${fotos.length})</span></h2><div class="thumbs-grid">` +
      fotos.map((src, k) => `<button type="button" class="thumb-btn" data-foto="${k}" aria-label="Ver foto ${k + 1} de ${fotos.length}">${imgHTML(src, '')}</button>`).join('') +
      '</div></section>';
  }
  function irParaSlide(k, suave = true) {
    const trilho = $('galTrilho');
    if (!trilho || !trilho.children[k]) return;
    trilho.scrollTo({ left: trilho.children[k].offsetLeft, behavior: suave ? 'smooth' : 'auto' });
  }
  function abrirVisor(k) {
    galeria.atual = (k + galeria.fotos.length) % galeria.fotos.length;
    const src = galeria.fotos[galeria.atual];
    $('visorImg').src = src;
    $('visorImg').alt = `Foto ${galeria.atual + 1} de ${galeria.fotos.length}`;
    $('visorContador').textContent = `${galeria.atual + 1} / ${galeria.fotos.length}`;
    $('visorCredito').textContent = `Imagem: ${galeria.fonte}`;
    $('visorOriginal').href = src;
    document.querySelectorAll('#visor .gal-nav').forEach((b) => { b.hidden = galeria.fotos.length < 2; });
    if (!$('visor').open) $('visor').showModal();
    irParaSlide(galeria.atual, false);
  }
  function montarGaleria(n, fotos) {
    galeria.fotos = fotos;
    galeria.fonte = n.fonte;
    galeria.atual = 0;
    const alvo = $('leitorFotos');
    if (!alvo) return;
    if (!fotos.length) {
      alvo.innerHTML = `<figure class="slide only">${imgHTML(ilustracao(n), 'Ilustração da categoria')}</figure>` +
        '<p class="reader-credit">Ilustração da categoria — esta reportagem não tem foto disponível.</p>';
      $('leitorMiniaturas').innerHTML = '';
      return;
    }
    alvo.innerHTML = galeriaHTML(fotos, n.fonte);
    $('leitorMiniaturas').innerHTML = miniaturasHTML(fotos);
    const trilho = $('galTrilho');
    trilho.addEventListener('scroll', debounce(() => {
      const k = Math.round(trilho.scrollLeft / Math.max(1, trilho.clientWidth));
      galeria.atual = Math.min(fotos.length - 1, Math.max(0, k));
      const c = $('galContador');
      if (c) c.textContent = `${galeria.atual + 1} / ${fotos.length}`;
    }, 60));
    trilho.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); irParaSlide(Math.min(fotos.length - 1, Math.max(0, galeria.atual + (e.key === 'ArrowRight' ? 1 : -1)))); }
    });
  }
  let linksPromise = null;
  const carregarLinks = () => (linksPromise ??= fetch('feed_links.json').then((r) => (r.ok ? r.json() : [])).catch(() => []));

  function abrirLeitor(i, { atualizarUrl = true } = {}) {
    const n = state.porIndice.get(Number(i));
    if (!n) return;
    const dlg = $('leitor');
    const cats = n.cats.map((c) => state.categorias[c]).join(' · ') || 'Em classificação';
    const foto = '<div id="leitorFotos" class="reader-media"></div>';
    const texto = n.texto ? '<div class="reader-full" id="leitorTexto"><p class="reader-text">Carregando o texto…</p></div>'
      : n.resumo ? `<p class="reader-text">${esc(n.resumo)}</p><p class="reader-note">Resumo publicado pela fonte. A reportagem completa está no site de origem.</p>`
        : '<p class="reader-text">O resumo desta notícia não está disponível. Leia a reportagem completa na fonte original.</p>';
    $('leitorConteudo').innerHTML =
      `${tagsHTML(n)}<h1 id="leitorTitulo">${esc(n.titulo)}</h1>${metaHTML(n)}${foto}${texto}<div id="leitorMiniaturas"></div>` +
      `<div class="reader-source"><div class="meta">Fonte: <strong>${esc(n.fonte)}</strong>${n.uf ? ' · ' + esc(NOME_UF[n.uf]) : ''} · ${esc(cats)}</div>` +
      `<div class="reader-actions"><a class="btn" id="leitorLink" href="${esc(n.url || '#')}" target="_blank" rel="noopener noreferrer"${n.url ? '' : ' aria-disabled="true"'}>Ler na fonte original ↗</a>` +
      `<button type="button" class="btn-ghost" id="compartilhar">Compartilhar</button></div></div>`;
    $('leitorConteudo').dataset.i = String(n.i);
    montarGaleria(n, n.img ? [n.img] : []);
    if (n.texto || n.nFotos > 1) {
      carregarDetalhe(n.i).then((t) => {
        if ($('leitorConteudo').dataset.i !== String(n.i)) return;
        if (Array.isArray(t.g) && t.g.length > 1) montarGaleria(n, t.g.map(urlSegura).filter(Boolean));
        const alvo = $('leitorTexto');
        if (!alvo) return;
        alvo.innerHTML = t && Array.isArray(t.p)
          ? t.p.map((p) => `<p class="reader-text">${esc(p)}</p>`).join('') +
            `<p class="reader-note">Texto reproduzido integralmente de <strong>${esc(n.fonte)}</strong>, sob a licença ${esc(t.l)}, que permite a reprodução com crédito.</p>`
          : (n.resumo ? `<p class="reader-text">${esc(n.resumo)}</p>` : '<p class="reader-text">Texto indisponível no momento. Leia na fonte original.</p>');
      });
    }
    if (!n.url) {
      carregarLinks().then((links) => {
        const u = urlSegura(links[n.i] || '');
        if (u && $('leitorConteudo').dataset.i === String(n.i)) { n.url = u; const a = $('leitorLink'); a.href = u; a.removeAttribute('aria-disabled'); }
      });
    }
    $('leitorLink').addEventListener('click', (e) => { if (e.currentTarget.getAttribute('aria-disabled') === 'true') e.preventDefault(); });
    $('compartilhar').addEventListener('click', async () => {
      const link = `${location.origin}${location.pathname}#noticia-${n.i}`;
      try {
        if (navigator.share) await navigator.share({ title: n.titulo, url: link });
        else { await navigator.clipboard.writeText(link); $('compartilhar').textContent = 'Link copiado ✓'; }
      } catch { /* compartilhamento cancelado */ }
    });
    if (!dlg.open) dlg.showModal();
    dlg.scrollTop = 0;
    if (atualizarUrl) history.pushState({ leitor: n.i }, '', `#noticia-${n.i}`);
  }
  function aoFecharLeitor() {
    if (history.state && history.state.leitor != null) history.back(); // volta para a URL de antes de abrir
    else if (location.hash.startsWith('#noticia-')) escreverHash();
  }

  // ---------- eventos ----------
  function ligarEventos() {
    $('busca').addEventListener('input', debounce((e) => definir({ q: e.target.value.trim() }), 160));
    $('formFiltros').addEventListener('submit', (e) => { e.preventDefault(); definir({ q: $('busca').value.trim() }, { rolar: true }); });
    $('formFiltros').addEventListener('reset', (e) => { e.preventDefault(); definir({ q: '', uf: '', cat: '', ano: '' }); });
    $('fEstado').addEventListener('change', (e) => definir({ uf: e.target.value }));
    $('fCategoria').addEventListener('change', (e) => definir({ cat: e.target.value }));
    $('fAno').addEventListener('change', (e) => definir({ ano: e.target.value }));
    $('mais').addEventListener('click', () => { state.limite += POR_PAGINA; renderLista(); });

    document.addEventListener('click', (e) => {
      const alvo = e.target.closest('[data-read],[data-uf],[data-cat],[data-limpar]');
      if (!alvo) return;
      if (alvo.dataset.read !== undefined) return abrirLeitor(alvo.dataset.read);
      if (alvo.dataset.limpar !== undefined) return definir({ q: '', uf: '', cat: '', ano: '' });
      if (alvo.dataset.uf !== undefined) return definir({ uf: state.filtro.uf === alvo.dataset.uf ? '' : alvo.dataset.uf }, { rolar: true });
      if (alvo.dataset.cat !== undefined && alvo.tagName === 'BUTTON') return definir({ cat: state.filtro.cat === alvo.dataset.cat ? '' : alvo.dataset.cat }, { rolar: true });
    });
    // Foto externa que não carrega: troca pela ilustração da categoria ou some.
    document.addEventListener('error', (e) => {
      const img = e.target;
      if (!(img instanceof HTMLImageElement)) return;
      if (img.dataset.fallback) { img.src = img.dataset.fallback; delete img.dataset.fallback; }
      else if (img.hasAttribute('data-hide-on-error')) (img.closest('.thumb') || img).remove();
      else if (img.closest('.slide, .thumb-btn')) img.replaceWith(Object.assign(document.createElement('span'), { className: 'img-off', textContent: 'Imagem indisponível' }));
    }, true);

    $('leitor').addEventListener('click', (e) => {
      const nav = e.target.closest('[data-gal]');
      if (nav) return irParaSlide(Math.min(galeria.fotos.length - 1, Math.max(0, galeria.atual + Number(nav.dataset.gal))));
      const foto = e.target.closest('[data-foto]');
      if (foto) abrirVisor(Number(foto.dataset.foto));
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
    let toqueX = null;
    $('visor').addEventListener('touchstart', (e) => { toqueX = e.touches[0].clientX; }, { passive: true });
    $('visor').addEventListener('touchend', (e) => {
      if (toqueX == null) return;
      const dx = e.changedTouches[0].clientX - toqueX;
      if (Math.abs(dx) > 40) abrirVisor(galeria.atual + (dx < 0 ? 1 : -1));
      toqueX = null;
    });
    $('fecharLeitor').addEventListener('click', () => $('leitor').close());
    $('leitor').addEventListener('close', aoFecharLeitor);
    $('leitor').addEventListener('click', (e) => { if (e.target === $('leitor')) $('leitor').close(); });
    window.addEventListener('popstate', () => {
      const h = lerHash();
      if (h.noticia != null) abrirLeitor(h.noticia, { atualizarUrl: false });
      else if ($('leitor').open) $('leitor').close();
    });
    window.addEventListener('hashchange', () => {
      const h = lerHash();
      if (h.noticia != null) return abrirLeitor(h.noticia, { atualizarUrl: false });
      if (['q', 'uf', 'cat', 'ano'].some((k) => h[k] !== state.filtro[k])) definir({ q: h.q, uf: h.uf, cat: h.cat, ano: h.ano });
    });
  }

  // ---------- carregamento ----------
  function esqueleto() {
    $('destaques').innerHTML = '<div class="skeleton sk-card"></div>'.repeat(3);
    $('lista').innerHTML = '<li class="skeleton sk-row"></li>'.repeat(5);
  }

  async function carregar() {
    esqueleto();
    try {
      const r = await fetch('feed.json');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const dados = await r.json();
      state.categorias = Array.isArray(dados.categorias) ? dados.categorias : [];
      state.noticias = (dados.noticias || []).map((n) => preparar(n, state.categorias))
        .sort((a, b) => (b.data?.getTime() || 0) - (a.data?.getTime() || 0));
      state.porIndice = new Map(state.noticias.map((n) => [n.i, n]));
      const quando = dados.atualizado_em ? new Date(dados.atualizado_em) : null;
      $('atualizado').textContent = quando && Number.isFinite(quando.getTime())
        ? `Atualizado em ${quando.toLocaleString('pt-BR', { dateStyle: 'long', timeStyle: 'short', timeZone: 'America/Sao_Paulo' })}`
        : 'Acervo carregado';
      preencherSelects();
      renderPainel();
      const h = lerHash();
      Object.assign(state.filtro, { q: h.q, uf: h.uf, cat: h.cat, ano: h.ano });
      aplicar();
      if (h.noticia != null) abrirLeitor(h.noticia, { atualizarUrl: false });
    } catch (err) {
      console.error(err);
      $('destaques').innerHTML = '';
      $('lista').innerHTML = '';
      $('atualizado').textContent = 'Não foi possível carregar o acervo.';
      const msg = $('mensagem');
      msg.hidden = false;
      msg.innerHTML = '<strong>As notícias não carregaram</strong>Verifique sua conexão e tente novamente.<br><button type="button" class="btn" id="tentar">Tentar de novo</button>';
      $('tentar').addEventListener('click', () => { msg.hidden = true; carregar(); }, { once: true });
    }
  }

  ligarEventos();
  carregar();
})();
