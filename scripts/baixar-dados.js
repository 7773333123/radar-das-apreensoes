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
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      fs.writeFileSync(destino, Buffer.from(await r.arrayBuffer()));
      return;
    } catch (e) {
      console.log(`Download de ${nome} falhou (${e.message}); tentativa ${k}/5`);
      if (k === 5) throw e;
      await new Promise((ok) => setTimeout(ok, 3000 * k));
    }
  }
}

// Acervo em partes (acervo.py): a parte "quente" (últimos 45 dias) e uma parte por ano, cada
// uma com o próprio pedaço do site em partes/<parte>/. Aqui as partes são juntadas em
// feed.json, feed-recente.json, feed_links.json e det/ (o mesmo que acervo.montar_site()).
function juntarPartes(origem) {
  const feeds = {};
  const links = {};
  const det = {};
  let recente = null;
  for (const parte of fs.readdirSync(origem).sort()) {
    const d = path.join(origem, parte);
    const ler = (f) => JSON.parse(fs.readFileSync(path.join(d, f), 'utf8'));
    if (fs.existsSync(path.join(d, 'feed.json'))) feeds[parte] = ler('feed.json');
    if (parte === 'quente' && fs.existsSync(path.join(d, 'feed-recente.json'))) recente = fs.readFileSync(path.join(d, 'feed-recente.json'));
    if (fs.existsSync(path.join(d, 'feed_links.json'))) Object.assign(links, ler('feed_links.json'));
    const pastaDet = path.join(d, 'det');
    if (fs.existsSync(pastaDet)) {
      for (const lote of fs.readdirSync(pastaDet)) Object.assign(det[lote] ??= {}, JSON.parse(fs.readFileSync(path.join(pastaDet, lote), 'utf8')));
    }
  }
  const nomes = Object.keys(feeds);
  if (!nomes.length) throw new Error('nenhuma parte do site encontrada');
  const feed = { ...(feeds.quente || feeds[nomes[0]]) };
  const vistos = new Set();
  feed.noticias = nomes.flatMap((n) => feeds[n].noticias || []).filter((x) => !vistos.has(x.i) && vistos.add(x.i))
    .sort((a, b) => (b.d || '').localeCompare(a.d || ''));
  feed.total = feed.noticias.length;
  fs.writeFileSync(path.join(RAIZ, 'feed.json'), JSON.stringify(feed));
  if (recente) fs.writeFileSync(path.join(RAIZ, 'feed-recente.json'), recente);
  fs.writeFileSync(path.join(RAIZ, 'feed_links.json'), JSON.stringify(links));
  fs.rmSync(path.join(RAIZ, 'det'), { recursive: true, force: true });
  fs.mkdirSync(path.join(RAIZ, 'det'));
  for (const [lote, conteudo] of Object.entries(det)) fs.writeFileSync(path.join(RAIZ, 'det', lote), JSON.stringify(conteudo));
  console.log(`Site montado de ${nomes.length} partes: ${feed.total} notícias`);
}

(async () => {
  const versao = JSON.parse(fs.readFileSync(path.join(RAIZ, 'dados_versao.json'), 'utf8'));
  if (!versao.site) throw new Error('dados_versao.json sem a versão do site');
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'radar-'));
  const pacotes = [versao.site, ...Object.values(versao.partes || {}).map((p) => p.site).filter(Boolean)];
  for (const nome of pacotes) {
    const tgz = path.join(tmp, nome);
    await baixar(nome, tgz);
    execFileSync('tar', ['-xzf', tgz, '-C', tmp], { stdio: 'inherit' });
  }
  if (fs.existsSync(path.join(tmp, 'partes'))) {
    juntarPartes(path.join(tmp, 'partes'));
  } else {  // pacote único (antes da divisão em partes)
    for (const f of ['feed.json', 'feed-recente.json', 'feed_links.json', 'det', 'dados']) {
      if (fs.existsSync(path.join(tmp, f))) fs.cpSync(path.join(tmp, f), path.join(RAIZ, f), { recursive: true });
    }
  }
  for (const f of ['feed.json', 'feed_links.json', 'det']) {
    if (!fs.existsSync(path.join(RAIZ, f))) throw new Error(`faltou ${f} no pacote ${versao.site}`);
  }
  // A Vercel publica a pasta public/: páginas, arquivos estáticos e os dados.
  // (As funções em api/ leem os dados da raiz, por includeFiles.)
  const PUB = path.join(RAIZ, 'public');
  fs.rmSync(PUB, { recursive: true, force: true });
  fs.mkdirSync(PUB);
  const estaticos = fs.readdirSync(RAIZ).filter((f) => /\.(html|txt|xml|webmanifest|ico)$/.test(f))
    .concat(['assets', 'img', 'feed.json', 'feed-recente.json', 'feed_links.json', 'det']);  // dados/ (planilhas) não é publicado
  for (const f of estaticos) {
    if (fs.existsSync(path.join(RAIZ, f))) fs.cpSync(path.join(RAIZ, f), path.join(PUB, f), { recursive: true });
  }
  console.log(`Dados do site prontos: ${pacotes.length} pacote(s) (versão de ${versao.atualizado_em}); public/: ${estaticos.length} itens`);
})().catch((e) => { console.error(e); process.exit(1); });
