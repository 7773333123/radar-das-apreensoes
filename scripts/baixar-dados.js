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

(async () => {
  const versao = JSON.parse(fs.readFileSync(path.join(RAIZ, 'dados_versao.json'), 'utf8'));
  if (!versao.site) throw new Error('dados_versao.json sem a versão do site');
  const tgz = path.join(require('os').tmpdir(), versao.site);
  await baixar(versao.site, tgz);
  execFileSync('tar', ['-xzf', tgz, '-C', RAIZ], { stdio: 'inherit' });
  for (const f of ['feed.json', 'feed_links.json', 'det', 'dados']) {
    if (!fs.existsSync(path.join(RAIZ, f))) throw new Error(`faltou ${f} no pacote ${versao.site}`);
  }
  // A Vercel publica a pasta public/: páginas, arquivos estáticos e os dados.
  // (As funções em api/ leem os dados da raiz, por includeFiles.)
  const PUB = path.join(RAIZ, 'public');
  fs.rmSync(PUB, { recursive: true, force: true });
  fs.mkdirSync(PUB);
  const estaticos = fs.readdirSync(RAIZ).filter((f) => /\.(html|txt|xml|webmanifest|ico)$/.test(f))
    .concat(['assets', 'img', 'feed.json', 'feed_links.json', 'det', 'dados']);
  for (const f of estaticos) {
    if (fs.existsSync(path.join(RAIZ, f))) fs.cpSync(path.join(RAIZ, f), path.join(PUB, f), { recursive: true });
  }
  console.log(`Dados do site prontos: ${versao.site} (versão de ${versao.atualizado_em}); public/: ${estaticos.length} itens`);
})().catch((e) => { console.error(e); process.exit(1); });
