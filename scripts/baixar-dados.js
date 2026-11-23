// Build da Vercel: baixa os dados do site (feed.json, feed_links.json, det/, dados/)
// da release "dados" do GitHub, na versão indicada em dados_versao.json.
// Assim esses arquivos gerados não precisam ficar no histórico do Git.
// Monta public/ (pasta publicada pela Vercel) com as páginas e os dados.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const RAIZ = path.join(__dirname, '..');
const REPO = '7773333123/radar-das-apreensoes';

async function baixar(nome, destino) {
  const url = `https://github.com/${REPO}/releases/download/dados/${nome}`;
  for (let k = 1; k <= 5; k++) {
    try {
      const r = await fetch(url, { redirect: 'follow' });
      if (r.status === 404) throw Object.assign(new Error(`HTTP 404: ${nome}`), { naoExiste: true });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      fs.writeFileSync(destino, Buffer.from(await r.arrayBuffer()));
      return;
    } catch (e) {
      console.log(`Download de ${nome} falhou (${e.message}); tentativa ${k}/5`);
      if (k === 5 || e.naoExiste) throw e;
      await new Promise((ok) => setTimeout(ok, 3000 * k));
    }
  }
}

// Acervo em partes (acervo.py): a parte "quente" (últimos 45 dias) e uma parte por ano, cada
// uma com o próprio pedaço do site em partes/<parte>/. Aqui as partes são juntadas.
// Memória: com centenas de milhares de notícias, nada é carregado em dobro — o feed é montado
// parte a parte e os detalhes (det/) são escritos um lote por vez.
function juntarPartes(pastas) {
  let base = null, recente = null;
  const links = {}, vistos = new Set(), noticias = [];
  for (const d of pastas) {
    const nome = path.basename(d);
    const arq = path.join(d, 'feed.json');
    if (fs.existsSync(arq)) {
      const f = JSON.parse(fs.readFileSync(arq, 'utf8'));
      const { noticias: lista, ...resto } = f;
      if (nome === 'quente' || !base) base = nome === 'quente' ? resto : (base || resto);
      for (const x of lista || []) if (!vistos.has(x.i)) { vistos.add(x.i); noticias.push(x); }
    }
    if (fs.existsSync(path.join(d, 'feed-recente.json')) && (nome === 'quente' || !recente)) {
      recente = JSON.parse(fs.readFileSync(path.join(d, 'feed-recente.json'), 'utf8'));
    }
    if (fs.existsSync(path.join(d, 'feed_links.json'))) Object.assign(links, JSON.parse(fs.readFileSync(path.join(d, 'feed_links.json'), 'utf8')));
  }
  if (!base) throw new Error('nenhuma parte do site encontrada');
  noticias.sort((a, b) => (b.d || '').localeCompare(a.d || ''));
  console.log(`Site montado de ${pastas.length} parte(s): ${noticias.length} notícias`);
  return { feed: { ...base, noticias, total: noticias.length }, recente, links };
}

const RESUMO_LISTA = 200;
const DIAS_FEED = 180;  // feed.json do navegador: últimos 180 dias
function cortarResumo(r) {
  if (!r || r.length <= RESUMO_LISTA) return r;
  return r.slice(0, RESUMO_LISTA).replace(/\s+\S*$/, '') + '…';
}
// Arquivo que o navegador baixa (busca, filtros, Observatório): só o necessário para listar e
// buscar. O link original, o resumo completo e os links das outras fontes vão para det/ (que o
// leitor e as páginas do servidor carregam ao abrir a notícia).
function enxugarParaNavegador(feed, recente) {
  const extras = {};  // lote -> { id: {u, r, o} }
  const enxuto = (n) => {
    const y = { ...n };
    if (n.u || (n.r && n.r.length > RESUMO_LISTA) || (n.o || []).some((o) => o[1])) {
      const d = ((extras[`${Number(n.i) % 256}.json`] ??= {})[String(n.i)] ??= {});
      if (n.u) d.u = n.u;
      if (n.r && n.r.length > RESUMO_LISTA) d.r = n.r;
      if ((n.o || []).some((o) => o[1])) d.o = n.o;
    }
    if (y.u) { delete y.u; y.uh = 1; }  // tem link original (o servidor busca a foto por ele)
    if (y.r) y.r = cortarResumo(y.r);
    if (y.o) y.o = y.o.map((o) => [o[0], '', o[2]]);
    return y;
  };
  // O navegador baixa só os últimos DIAS_FEED dias (feed.json); o resto fica em um arquivo
  // por ano (anos/AAAA.json), carregado quando o leitor escolhe um ano, busca em todo o
  // acervo ou abre um período antigo no Observatório. anos/indice.json traz as contagens
  // por ano e mês (filtros, Relatórios) e anos/ids.json diz em que ano está cada notícia.
  const corte = new Date(Date.now() - DIAS_FEED * 864e5).toISOString().slice(0, 10);
  const { noticias: todas, ...cabeca } = feed;
  const recentes = [], porAno = {}, ids = {}, contAno = {}, contMes = {};
  for (let k = 0; k < todas.length; k++) {
    const n = enxuto(todas[k]);
    todas[k] = null;  // libera a versão completa
    const d = n.d || '';
    if (d >= '2000') {
      contAno[d.slice(0, 4)] = (contAno[d.slice(0, 4)] || 0) + 1;
      contMes[d.slice(0, 7)] = (contMes[d.slice(0, 7)] || 0) + 1;
    }
    if (!d || d >= corte) { recentes.push(n); continue; }
    const a = d.slice(0, 4);
    (porAno[a] ??= []).push(n);
    (ids[a] ??= []).push(n.i);
  }
  const saida = { 'feed.json': JSON.stringify({ ...cabeca, noticias: recentes, recorte: corte }) };
  for (const [a, lista] of Object.entries(porAno)) { saida[`anos/${a}.json`] = JSON.stringify({ ano: a, noticias: lista }); porAno[a] = null; }
  saida['anos/indice.json'] = JSON.stringify({ recorte: corte, atualizado_em: feed.atualizado_em, total: todas.length,
    anos: contAno, meses: contMes, arquivos: Object.keys(porAno).sort() });
  saida['anos/ids.json'] = JSON.stringify(ids);
  if (recente) saida['feed-recente.json'] = JSON.stringify({ ...recente, noticias: recente.noticias.map(enxuto) });
  // agora.json: só as 40 mais novas (poucos KB). A página confere a cada minuto e, se chegou
  // notícia, busca o feed-recente.json (pesado) para atualizar tudo.
  if (recente) {
    const novas = [...recente.noticias].sort((a, b) => String(b.d || '').localeCompare(String(a.d || ''))).slice(0, 40)
      .map((n) => ({ i: n.i, t: n.t, d: n.d }));
    saida['agora.json'] = JSON.stringify({ atualizado_em: recente.atualizado_em || feed.atualizado_em,
      gerado_em: recente.gerado_em || feed.gerado_em || null, noticias: novas });
  }
  console.log(`Feed para o navegador: ${(saida['feed.json'].length / 1e6).toFixed(1)} MB, ${recentes.length} notícias desde ${corte}; ` +
    `anos à parte: ${Object.keys(porAno).sort().join(', ')}`);
  return { saida, extras };
}

// det/<lote>.json: junta o lote de todas as partes e os campos completos (extras), um lote por vez.
function escreverDet(pastasDet, extras, destino) {
  fs.mkdirSync(destino, { recursive: true });
  const lotes = new Set(Object.keys(extras));
  for (const p of pastasDet) for (const f of fs.readdirSync(p)) lotes.add(f);
  for (const lote of lotes) {
    const obj = {};
    for (const p of pastasDet) {
      const arq = path.join(p, lote);
      if (fs.existsSync(arq)) Object.assign(obj, JSON.parse(fs.readFileSync(arq, 'utf8')));
    }
    for (const [i, campos] of Object.entries(extras[lote] || {})) Object.assign(obj[i] ??= {}, campos);
    fs.writeFileSync(path.join(destino, lote), JSON.stringify(obj));
    delete extras[lote];
  }
  return lotes.size;
}

// Ponteiro mais novo da main: a coleta apaga os pacotes antigos ao gravar, então um build que
// começa com um ponteiro velho (deploy de um commit anterior, branch desatualizada) busca o atual.
async function ponteiroAtual() {
  const r = await fetch(`https://raw.githubusercontent.com/${REPO}/main/dados_versao.json?t=${Date.now()}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`ponteiro da main: HTTP ${r.status}`);
  return r.json();
}

async function baixarPacotes(versao) {
  if (!versao.site) throw new Error('dados_versao.json sem a versão do site');
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'radar-'));
  const pacotes = [versao.site, ...Object.values(versao.partes || {}).map((p) => p.site).filter(Boolean)];
  try {
    for (const nome of pacotes) {
      const tgz = path.join(tmp, nome);
      await baixar(nome, tgz);
      execFileSync('tar', ['-xzf', tgz, '-C', tmp], { stdio: 'inherit' });
      fs.rmSync(tgz);
    }
  } catch (e) {
    fs.rmSync(tmp, { recursive: true, force: true });
    throw e;
  }
  return { tmp, pacotes };
}

(async () => {
  let versao = JSON.parse(fs.readFileSync(path.join(RAIZ, 'dados_versao.json'), 'utf8'));
  let baixado = null;
  for (let tentativa = 1; !baixado; tentativa++) {
    try {
      baixado = await baixarPacotes(versao);
    } catch (e) {
      if (!e.naoExiste || tentativa >= 4) throw e;
      console.log(`Pacote já substituído por uma gravação mais nova; usando o ponteiro atual da main (tentativa ${tentativa}).`);
      versao = await ponteiroAtual();
    }
  }
  const { tmp, pacotes } = baixado;
  // Partes (partes/<parte>/) ou pacote único antigo (tudo na raiz do pacote).
  const pastas = fs.existsSync(path.join(tmp, 'partes'))
    ? fs.readdirSync(path.join(tmp, 'partes')).sort().map((p) => path.join(tmp, 'partes', p)) : [tmp];
  const { feed, recente, links } = juntarPartes(pastas);
  const { saida, extras } = enxugarParaNavegador(feed, recente);
  // A Vercel publica a pasta public/: páginas, arquivos estáticos e os dados.
  // (As funções em api/ buscam estes mesmos arquivos publicados, por HTTP.)
  const PUB = path.join(RAIZ, 'public');
  fs.rmSync(PUB, { recursive: true, force: true });
  fs.mkdirSync(PUB);
  const estaticos = fs.readdirSync(RAIZ).filter((f) => /\.(html|txt|xml|webmanifest|ico)$/.test(f)).concat(['assets', 'img']);
  for (const f of estaticos) {
    if (fs.existsSync(path.join(RAIZ, f))) fs.cpSync(path.join(RAIZ, f), path.join(PUB, f), { recursive: true });
  }
  for (const [nome, conteudo] of Object.entries(saida)) {
    fs.mkdirSync(path.dirname(path.join(PUB, nome)), { recursive: true });
    fs.writeFileSync(path.join(PUB, nome), conteudo);
  }
  fs.writeFileSync(path.join(PUB, 'feed_links.json'), JSON.stringify(links));
  const nLotes = escreverDet(pastas.map((d) => path.join(d, 'det')).filter((d) => fs.existsSync(d)), extras, path.join(PUB, 'det'));
  fs.rmSync(tmp, { recursive: true, force: true });
  console.log(`Dados do site prontos: ${pacotes.length} pacote(s) (versão de ${versao.atualizado_em}); det: ${nLotes} lotes; ` +
    `memória máxima ${(process.resourceUsage().maxRSS / 1024).toFixed(0)} MB`);
})().catch((e) => { console.error(e); process.exit(1); });
