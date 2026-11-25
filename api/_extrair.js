// Leitura da matéria original na hora (quando a notícia ainda não passou pela leitura em lote).
// Mesmas regras de ler_materias.py: fotos só da matéria (sem anúncios, logos, miniaturas de
// outras notícias), trecho de 50-70% sempre terminando em frase completa, texto integral de
// órgãos oficiais, nome de preso vira iniciais (imprensa). Arquivos com "_" não viram rota na Vercel.

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';
const MAX_FOTOS = 10;
const OFICIAL = /\.(?:gov|jus|mp|leg|def)\.br$/i;

const NAO_FOTO = /^https?:\/\/i\.s3\.glbimg\.com\/|midia-de-distribuicao|(?:^|[\/_-])(?:share|default|padrao|og-?image|ogimage|fallback|no-?image|sem-?imagem)[\w-]*\.(?:png|jpe?g|webp)|logo|icon|icone|avatar|sprite|banner|placeholder|blank|pixel|spacer|loading|selo|whatsapp-share|\/ads?\/|publicidade|video\.glbimg|\/x240\/|\.svg(?:$|\?)|\.gif(?:$|\?)|gravatar|emoji|badge|flag/i;
const DOMINIO_ANUNCIO = /doubleclick|googlesyndication|googleadservices|adservice|adsystem|taboola|outbrain|teads|criteo|adnxs|rubiconproject|pubmatic|smartadserver|facebook\.com\/tr|scorecardresearch|\/ads?\/|\/banners?\/|\/publicidade\/|\/anuncios?\/|\/patrocin/i;
const MINIATURA = /[-_](?:\d{2,3})x(?:\d{2,3})\.(?:jpe?g|png|webp)|\/thumbs?\/|[-_]thumb|\/(?:50|75|100|120|150|160|180|200)x|\/fit-in\/(?:\d{2,3})x|w=(?:\d{2,3})\b(?!\d)/i;
const CONTEINER_ALHEIO = /\b(?:ads?|adv|advert\w*|anuncio\w*|publicidade|banner\w*|sponsor\w*|patrocin\w*|dfp|gpt|teads|taboola|outbrain|related\w*|relacionad\w*|recomend\w*|recommend\w*|mais-?lidas|most-?read|leia-?tamb\w*|veja-?tamb\w*|saiba-?mais|sidebar|aside|widget\w*|newsletter|promo\w*|carousel-?news|ultimas|latest|trending|shopping|video-?playlist|playlist|feed-?item|card-?news|outras-?noticias|author|autor)\b/i;
const FIM_DA_MATERIA = /<(?:div|section|aside|ul|h2|h3)\b[^>]*(?:class|id)="[^"]*(?:related|relacionad|recomend|recommend|mais-?lidas|most-?read|leia-?tamb|veja-?tamb|outras-?noticias|taboola|outbrain|comments?|comentarios)[^"]*"|>\s*(?:Leia (?:também|mais)|Veja também|Mais lidas|Notícias relacionadas|Últimas notícias|Você pode gostar)\s*</i;
const ASSUNTO_ALHEIO = /futebol|jogador|campeonato|partida|gol\b|t[ée]cnico do|torcida|est[áa]dio|novela|cantor|cantora|show\b|reality|bbb\b|receita de|hor[óo]scopo|loteria|mega-?sena|cupom|oferta|promo[çc][ãa]o/i;
const POLICIAL = /pol[íi]cia|apreen|droga|maconha|coca[íi]na|arma|muni[çc]|presos?|pris[ãa]o|opera[çc][ãa]o|ve[íi]culo|carga|contrabando|PRF|PF|PM|PC|delegacia|fronteira|rodovia|BR-|viatura|suspeit/i;
const RUIDO = /^(?:Leia (?:tamb[ée]m|mais)|Veja (?:tamb[ée]m|mais|o v[íi]deo)|Siga|Assine|Clique|Receba|Inscreva|Participe|Compartilhe|Acesse|Baixe|Entre (?:no|em) nosso|Publicidade|Continua (?:depois|ap[óo]s)|Foto:|Imagem:|Cr[ée]dito|Reprodu[çc][ãa]o|Por\s+\w+\s*$|Atualizad[oa]|Publicad[oa] em|A utiliza[çc][ãa]o deste site|Os coment[áa]rios n[ãa]o representam|Veja nossas not[íi]cias|.*(?:Todos os direitos reservados|©|Copyright|Pol[íi]tica de Privacidade|Termos de [Uu]so|cookies))/i;
const CONTATO = /^(?:Comunica[çc][ãa]o Social|Assessoria de|Ascom|Tel\.?:|E-?mail:|Fonte:|Fotos?:|@)/i;
const PONTO_FINAL = /[.!?…:;)"”»]$/;

const ENTIDADES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', hellip: '…', laquo: '«', raquo: '»',
  ldquo: '“', rdquo: '”', lsquo: '‘', rsquo: '’', ordf: 'ª', ordm: 'º', deg: '°' };
const decodificar = (t) => String(t || '').replace(/&(#x?[0-9a-f]+|\w+);/gi, (m, e) => {
  if (e[0] === '#') { const n = e[1].toLowerCase() === 'x' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10); return Number.isFinite(n) ? String.fromCodePoint(n) : m; }
  const k = e.toLowerCase();
  if (ENTIDADES[k]) return ENTIDADES[k];
  const acento = { aacute: 'á', eacute: 'é', iacute: 'í', oacute: 'ó', uacute: 'ú', acirc: 'â', ecirc: 'ê', ocirc: 'ô', atilde: 'ã', otilde: 'õ', ccedil: 'ç', agrave: 'à', uuml: 'ü' }[k];
  if (acento) return e[0] === e[0].toUpperCase() ? acento.toUpperCase() : acento;
  return m;
});
const limpar = (f) => decodificar(String(f || '').replace(/<br\s*\/?>/gi, ' ').replace(/<[^>]+>/g, '')).replace(/\s+/g, ' ').trim();
const absoluta = (u, base) => { if (!u || !String(u).trim()) return ''; try { const x = new URL(decodificar(u).trim(), base); return /^https?:$/.test(x.protocol) ? x.href : ''; } catch { return ''; } };

// ---------- rede ----------
// Segurança (24/11/2026): o servidor só busca páginas públicas da internet. Endereço interno (localhost,
// rede privada, metadados da nuvem) é recusado, inclusive quando chega por redirecionamento.
function enderecoPublico(u) {
  let x;
  try { x = new URL(u); } catch { return false; }
  if (!/^https?:$/.test(x.protocol) || x.username || x.password) return false;
  const h = x.hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (!h || h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.local') || h.endsWith('.internal') || !h.includes('.') && !h.includes(':')) return false;
  if (/^\d+$/.test(h) || /^0x/i.test(h)) return false;  // IP escrito como número
  const v4 = h.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/);
  if (v4) {
    const [a, b] = [Number(v4[1]), Number(v4[2])];
    if (a === 0 || a === 10 || a === 127 || a >= 224 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31)
      || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127)) return false;
  }
  if (h.includes(':') && (h === '::1' || h === '::' || /^f[cd]/.test(h) || /^fe[89ab]/.test(h) || h.startsWith('::ffff:'))) return false;
  return true;
}

async function baixar(url, { timeout = 7000, limite = 2_500_000, metodo = 'GET', corpo, cabecalhos = {} } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    let r;
    for (let saltos = 0; ; saltos++) {  // segue no máximo 5 redirecionamentos, conferindo cada destino
      if (!enderecoPublico(url)) throw new Error('endereço não público');
      r = await fetch(url, { method: metodo, body: corpo, redirect: 'manual', signal: ctrl.signal,
        headers: { 'User-Agent': UA, 'Accept-Language': 'pt-BR,pt;q=0.9', Accept: 'text/html,application/xhtml+xml,*/*;q=0.8', ...cabecalhos } });
      const destino = r.status >= 300 && r.status < 400 && r.headers.get('location');
      if (!destino) break;
      if (saltos >= 5) throw new Error('redirecionamentos demais');
      url = new URL(destino, url).href;
      if (r.status !== 307 && r.status !== 308) { metodo = 'GET'; corpo = undefined; }
    }
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const buf = new Uint8Array(await r.arrayBuffer()).slice(0, limite);
    // Charset: cabeçalho, depois <meta charset> (muitos sites brasileiros ainda usam ISO-8859-1).
    let cs = (r.headers.get('content-type') || '').match(/charset=([\w-]+)/i)?.[1];
    if (!cs) cs = new TextDecoder('latin1').decode(buf.slice(0, 4000)).match(/<meta[^>]+charset=["']?([\w-]+)/i)?.[1];
    let texto;
    try { texto = new TextDecoder(cs || 'utf-8').decode(buf); } catch { texto = new TextDecoder('utf-8').decode(buf); }
    return { url: r.url || url, texto };
  } finally { clearTimeout(t); }
}

// Link do Google Notícias -> link do veículo (mesmo método de recuperar_links.py).
async function decodificarGoogle(url) {
  const token = (url.split('?')[0].replace(/\/$/, '').split('/').pop() || '');
  if (!/^[A-Za-z0-9_-]{20,}$/.test(token)) return '';
  try {
    const { texto } = await baixar(`https://news.google.com/rss/articles/${token}?hl=pt-BR&gl=BR&ceid=BR:pt-419`, { timeout: 6000, limite: 3_000_000 });
    const n = decodificar(texto).replace(/\\"/g, '"');
    const sg = n.match(/data-n-a-sg\s*=\s*["']([^"']+)/)?.[1];
    const ts = n.match(/data-n-a-ts\s*=\s*["']?(\d+)/)?.[1];
    if (!sg) return '';
    const pedido = ['garturlreq', [['X', 'X', ['X', 'X'], null, null, 1, 1, 'US:en', null, 1, null, null, null, null, null, 0, 1],
      'X', 'X', 1, [1, 1, 1], 1, 1, null, 0, 0, null, 0], token, Number(ts || 0), sg];
    const corpo = 'f.req=' + encodeURIComponent(JSON.stringify([[['Fbv4je', JSON.stringify(pedido), null, 'generic']]]));
    const { texto: resp } = await baixar('https://news.google.com/_/DotsSplashUi/data/batchexecute', { metodo: 'POST', corpo, timeout: 6000,
      cabecalhos: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' } });
    try {
      const u = JSON.parse(JSON.parse(resp.split('\n\n')[1])[0][2])[1];
      if (/^https?:\/\//.test(u) && !/google\.com/.test(u)) return u;
    } catch { /* formato alternativo abaixo */ }
    const m = resp.match(/https?:\/\/(?![^"\\]*google\.com)[^"\\\s<>]+/);
    return m ? m[0] : '';
  } catch { return ''; }
}

// ---------- página ----------
function meta(pagina, nomes) {
  for (const nome of nomes) {
    const re1 = new RegExp(`<meta[^>]+(?:property|name)=["']${nome}["'][^>]*content=["']([^"']+)`, 'i');
    const re2 = new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]*(?:property|name)=["']${nome}["']`, 'i');
    const m = pagina.match(re1) || pagina.match(re2);
    if (m) return decodificar(m[1]);
  }
  return '';
}

function regiaoDaMateria(pagina) {
  for (const p of [/itemprop="articleBody"[^>]*>/i, /property="rnews:articleBody"[^>]*>/i, /<article\b[^>]*>/i,
    /class="[^"]*(?:post-content|entry-content|materia-conteudo|content-text|article-body|news-body|single-content|td-post-content|conteudo-materia|texto-materia|noticia-conteudo|texto)[^"]*"/i]) {
    const m = pagina.match(p);
    if (!m) continue;
    const ini = m.index;
    const fimArtigo = pagina.indexOf('</article>', ini);
    let trecho = pagina.slice(ini, fimArtigo > 0 ? fimArtigo : ini + 200_000);
    const corte = trecho.slice(200).search(FIM_DA_MATERIA);
    if (corte >= 0) trecho = trecho.slice(0, corte + 200);
    return trecho;
  }
  return '';
}

function melhorDoSrcset(srcset) {
  const opcoes = String(srcset || '').split(',').map((p) => p.trim().split(/\s+/)).filter((b) => b[0])
    .map((b) => [/^\d+w$/.test(b[1] || '') ? parseInt(b[1], 10) : 0, b[0]]);
  const ate = opcoes.filter((o) => o[0] <= 1200);
  const lista = ate.length ? ate : opcoes;
  return lista.length ? lista.sort((a, b) => b[0] - a[0])[0][1] : '';
}

const palavras = (t) => new Set((String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().match(/[a-z0-9]{4,}/g) || []));
function fotoAlheia(url, contexto, legenda, titulo) {
  if (!url || url.startsWith('data:') || NAO_FOTO.test(url) || DOMINIO_ANUNCIO.test(url) || MINIATURA.test(url)) return true;
  if (CONTEINER_ALHEIO.test(contexto)) return true;
  if (legenda) {
    if (ASSUNTO_ALHEIO.test(legenda) && !POLICIAL.test(legenda)) return true;
    const pl = palavras(legenda);
    if (titulo && pl.size >= 4 && ![...pl].some((w) => palavras(titulo).has(w)) && !POLICIAL.test(legenda)) return true;
  }
  return false;
}

function fotosDaMateria(pagina, base, titulo) {
  const regiao = regiaoDaMateria(pagina);
  if (!regiao) return [];
  const fotos = [];
  const pilha = [];
  const re = /<(\/?)(div|section|aside|figure|li|ul|a|span|p)\b[^>]*>|<(?:amp-)?img\b[^>]*>/gi;
  let m;
  while ((m = re.exec(regiao))) {
    const tag = m[0];
    if (m[2]) {
      const nome = m[2].toLowerCase();
      if (m[1]) { for (let k = pilha.length - 1; k >= 0; k--) if (pilha[k][0] === nome) { pilha.length = k; break; } }
      else if (!tag.endsWith('/>')) pilha.push([nome, tag]);
      continue;
    }
    const at = {};
    for (const [, k, , v] of tag.matchAll(/([\w:-]+)\s*=\s*(["'])(.*?)\2/gs)) at[k.toLowerCase()] = decodificar(v);
    const url = melhorDoSrcset(at.srcset || at['data-srcset']) || at['data-src'] || at['data-lazy-src'] || at['data-original'] || at.src || '';
    const w = parseInt(at.width, 10), h = parseInt(at.height, 10);
    if ((w && w < 300) || (h && h < 200)) continue;
    const contexto = pilha.slice(-6).map((x) => x[1]).join(' ');
    const link = [...pilha].reverse().find((x) => x[0] === 'a');
    const destino = link && link[1].match(/href="([^"]+)"/);
    if (destino && !/\.(?:jpe?g|png|webp|gif)(?:\?|$)/i.test(destino[1])) continue; // miniatura de outra notícia
    const depois = regiao.slice(re.lastIndex, re.lastIndex + 800);
    const cap = depois.match(/<figcaption\b[^>]*>([\s\S]*?)<\/figcaption>/i);
    const legenda = [at.alt, at.title, cap ? limpar(cap[1]) : ''].filter(Boolean).join(' ');
    if (fotoAlheia(url, `${contexto} ${at.class || ''}`, legenda, titulo)) continue;
    const abs = absoluta(url, base);
    if (abs) fotos.push(abs);
  }
  return fotos;
}

function imagemJsonld(pagina, base) {
  for (const m of pagina.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)) {
    let dados;
    try { dados = JSON.parse(m[1].trim()); } catch { continue; }
    const pilha = [dados];
    while (pilha.length) {
      const it = pilha.pop();
      if (Array.isArray(it)) { pilha.push(...it); continue; }
      if (!it || typeof it !== 'object') continue;
      const tipos = [].concat(it['@type'] || []);
      if (tipos.some((t) => /Article/.test(t))) {
        for (let c of [].concat(it.image || it.thumbnailUrl || [])) {
          c = typeof c === 'object' ? c.url : c;
          const abs = typeof c === 'string' ? absoluta(c, base) : '';
          if (abs) return abs;
        }
      }
      pilha.push(...Object.values(it).filter((v) => v && typeof v === 'object'));
    }
  }
  return '';
}

function semRepetir(urls) {
  const vistos = new Set(), saida = [];
  for (const u of urls) {
    if (!u || !/^https?:\/\//.test(u)) continue;
    const chave = u.replace(/[?#].*$/, '').split('/').pop().toLowerCase().replace(/-\d{2,4}x\d{2,4}(?=\.\w+$)/, '');
    if (!vistos.has(chave)) { vistos.add(chave); saida.push(u); }
  }
  return saida.slice(0, MAX_FOTOS);
}

// ---------- texto ----------
function corpoDaMateria(pagina) {
  for (const p of [/property="rnews:articleBody"[^>]*>([\s\S]*?)<\/div>\s*<\/div>/i, /itemprop="articleBody"[^>]*>([\s\S]*?)<\/(?:div|section|article)>/i, /<article\b[^>]*>([\s\S]*?)<\/article>/i]) {
    const m = pagina.match(p);
    if (!m) continue;
    const ps = [...m[1].matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/gi)].map((x) => limpar(x[1])).filter((x) => x.length > 1 && !CONTATO.test(x));
    if (ps.reduce((s, x) => s + x.length, 0) > 200) return ps.slice(0, 80);
  }
  let melhor = [];
  for (const b of pagina.matchAll(/<(?:div|section|article)\b[^>]*>((?:(?!<\/?(?:div|section|article)\b)[\s\S])*?)<\/(?:div|section|article)>/gi)) {
    const ps = [...b[1].matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/gi)].map((x) => limpar(x[1])).filter((x) => x.length > 40 && !CONTATO.test(x));
    if (ps.join('').length > melhor.join('').length) melhor = ps;
  }
  return melhor.join('').length > 400 ? melhor.slice(0, 80) : [];
}

function corpoLimpo(ps) {
  const saida = [];
  let semPonto = 0;
  for (let p of ps) {
    p = p.trim();
    if (!p || RUIDO.test(p) || CONTATO.test(p) || (p.match(/\|/g) || []).length > 1) continue;
    if (!PONTO_FINAL.test(p) && p.length < 160) {
      semPonto += 1;
      if (saida.length >= 2 && semPonto >= 2) break; // lista de outras notícias
      continue; // intertítulo
    }
    semPonto = 0;
    saida.push(p);
  }
  return saida.join('').length >= 200 ? saida : [];
}

// 70% da reportagem, nunca menos de 50% (frase longa no limite entra, até 90%), sempre terminando em frase.
function trecho(ps) {
  const limpos = corpoLimpo(ps);
  const corpo = limpos.reduce((s, p) => s + p.length, 0);
  if (!corpo) return { tr: '', tt: 0 };
  const max = corpo * 0.7;
  const partes = [];
  let total = 0;
  for (const p of limpos) {
    if (p.length < 40) continue;
    if (total + p.length > max) {
      const frases = p.split(/(?<=[.!?…])\s+(?=\S)/);
      let corte = '';
      for (const f of frases) {
        const novo = (corte + ' ' + f).trim();
        if (total + novo.length <= max) { corte = novo; continue; }
        if (total + corte.length < 0.5 * corpo && total + novo.length <= 0.9 * corpo) { corte = novo; continue; }
        break;
      }
      if (corte) partes.push(corte);
      break;
    }
    partes.push(p);
    total += p.length + 2;
  }
  return { tr: fecharFrase(partes.join('\n\n')), tt: corpo };
}

function fecharFrase(t) {
  t = String(t || '').replace(/\s*(?:\[\s*(?:…|\.\.\.)\s*\]|…|\.{3,}|(?:Leia|Saiba|Veja) mais\W*|Continue lendo\W*)\s*$/i, '').trim();
  if (!t) return '';
  if (/[.!?]["”»’)\]]*$/.test(t)) return t;
  const fins = [...t.matchAll(/[.!?]["”»’)\]]*(?=\s|$)/g)];
  return fins.length ? t.slice(0, fins[fins.length - 1].index + fins[fins.length - 1][0].length) : '';
}

// Nome completo de pessoa presa/suspeita -> iniciais (só imprensa; notas oficiais ficam como o órgão publicou).
const NOME = "([A-ZÁÉÍÓÚÂÊÔÃÕ][a-záéíóúâêôãõçü']+(?:\\s+(?:(?:d[aeo]s?|e)\\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕ][a-záéíóúâêôãõçü']+){1,5})";
const NAO_PESSOA = /Pol[íi]cia|Militar|Civil|Federal|Rodovi|Receita|Delegacia|Batalh|Opera[çc]|Justi[çc]a|Minist|Secretaria|Tribunal|Governo|Prefeitura|Estado|Rua|Avenida|Bairro|Rodovia|Distrito|Comando|Grupo|Centro|Jardim|Vila|Parque|Hospital|Unidade/;
function iniciais(nome) {
  return nome.split(/\s+/).filter((w) => !/^(?:d[aeo]s?|e)$/i.test(w)).map((w) => w[0].toUpperCase() + '.').join(' ');
}
function anonimizar(texto) {
  const padroes = [
    new RegExp(NOME + ',?\\s+(?:de\\s+|com\\s+)?\\d{2}\\s+anos', 'g'),
    new RegExp(NOME + '\\s*\\(\\d{2}(?:\\s+anos)?\\)', 'g'),
    new RegExp('(?:identificad[oa]s? como|suspeit[oa]s?|pres[oa]s?|acusad[oa]s?|investigad[oa]s?|detid[oa]s?|conhecid[oa] como|chamad[oa]|nome de)\\s+' + NOME, 'g'),
  ];
  const nomes = new Set();
  for (const re of padroes) for (const m of texto.matchAll(re)) if (!NAO_PESSOA.test(m[1]) && m[1].split(/\s+/).length >= 2) nomes.add(m[1]);
  for (const n of [...nomes].sort((a, b) => b.length - a.length)) texto = texto.split(n).join(iniciais(n));
  return texto;
}

function corpoEstruturado(pagina) {
  const regiao = regiaoDaMateria(pagina);
  if (!regiao) return [];
  const saida = [];
  for (const m of regiao.matchAll(/<(p|h2|h3|h4|li|blockquote)\b[^>]*>([\s\S]*?)<\/\1>/gi)) {
    const tag = m[1].toLowerCase(), t = limpar(m[2]);
    if (t.length < 2 || CONTATO.test(t) || RUIDO.test(t)) continue;
    saida.push(/^h/.test(tag) ? '## ' + t : tag === 'li' ? '• ' + t : t);
  }
  while (saida.length && saida[saida.length - 1].startsWith('## ')) saida.pop();
  return saida.filter((x) => !x.startsWith('## ')).join('').length >= 200 ? saida.slice(0, 60) : [];
}

// ---------- principal ----------
async function lerMateria(url, titulo = '') {
  const { url: final, texto: pagina } = await baixar(url);
  const host = (() => { try { return new URL(final).hostname; } catch { return ''; } })();
  const principal = absoluta(meta(pagina, ['og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src']), final)
    || imagemJsonld(pagina, final);
  const fotos = semRepetir([principal, ...fotosDaMateria(pagina, final, titulo)].filter((u) => u && !NAO_FOTO.test(u) && !DOMINIO_ANUNCIO.test(u)));
  const saida = { u: final, img: fotos[0] || '', g: fotos };
  const ps = corpoDaMateria(pagina);
  if (OFICIAL.test(host)) {
    const p = corpoEstruturado(pagina);
    if (p.length) { saida.p = p; saida.l = 'oficial'; }
  }
  if (!saida.p) {
    const { tr, tt } = trecho(ps);
    if (tr) { saida.tr = OFICIAL.test(host) ? tr : anonimizar(tr); saida.tt = tt; }
    else {
      const desc = fecharFrase(meta(pagina, ['og:description', 'description', 'twitter:description']));
      if (desc.length >= 60) saida.tr = OFICIAL.test(host) ? desc : anonimizar(desc);
    }
  }
  return saida;
}

async function lerNoticia(item, linkGoogle) {
  let url = item.u || '';
  if (!url && linkGoogle) url = await decodificarGoogle(linkGoogle);
  if (!url) return null;
  return lerMateria(url, item.t || '');
}

module.exports = { lerNoticia, lerMateria, decodificarGoogle, anonimizar, fecharFrase };
