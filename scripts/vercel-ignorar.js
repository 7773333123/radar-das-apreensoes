#!/usr/bin/env node
// Vercel "ignoreCommand": decide se este commit gera uma publicação nova (23/11/2026).
// Saída 0 = pular a publicação; saída 1 = publicar.
//
// Por quê: a cada hora entram ~22 commits no main (Wayback por ano, juiz de duplicatas, coletas,
// regeneração por ano). A Vercel publica um de cada vez, a fila crescia e a faixa AGORA chegava a
// 40+ min de atraso. Só a parte QUENTE (página inicial, faixa AGORA, notícias recentes) precisa de
// publicação imediata; as partes de anos antigos entram junto na próxima publicação da quente
// (a coleta expressa troca a quente a cada ~8 min), porque o build baixa sempre a versão atual de
// todas as partes (scripts/baixar-dados.js).
//
// Publica quando: branch main E (mudou algum arquivo que não é dado/cursor — na hora — OU mudou o "site"
// da parte quente em dados_versao.json e já passaram 30 min da última publicação (VERCEL_GIT_PREVIOUS_SHA)).
// Na dúvida (sem histórico para comparar), publica.
const { execSync } = require('child_process');
const INTERVALO_MIN = 30;  // publicação de dados no máximo a cada 30 min (custo da Vercel, 25/11/2026)

if (process.env.VERCEL_GIT_COMMIT_REF !== 'main') process.exit(0);

const sh = (cmd) => execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
const existe = (sha) => { try { sh(`git cat-file -e ${sha}^{commit}`); return true; } catch { return false; } };

let base = process.env.VERCEL_GIT_PREVIOUS_SHA || '';
// O clone da Vercel é raso (10 commits); entram ~20 commits por hora. Busca mais histórico para achar a
// última publicação (repositório público).
if (base && !existe(base)) { try { sh('git fetch -q --deepen=150 origin'); } catch { /* segue */ } }
const temBase = Boolean(base) && existe(base);
if (!temBase) base = 'HEAD^';
if (!existe(base)) process.exit(1);

// Arquivos de dados/estado das coletas: não mudam o site por si.
const SO_DADOS = /^(dados_versao|capas_ia|revisao_titulos|marcas_dagua|duplicatas_suspeitas|feeds_saude|buscadores_cursor|cobertura_historica|agencia_cursor|historico_cursor|juiz_[a-z_]+|wayback_cursor_\d{4}|[a-z_]*_cursor(_\d{4})?)\.json$/;

let arquivos;
try {
  arquivos = sh(`git diff --name-only ${base} HEAD`).split('\n').filter(Boolean);
} catch {
  process.exit(1);
}
if (arquivos.some((f) => !SO_DADOS.test(f))) process.exit(1); // código, página ou regra mudou

const siteQuente = (ref) => {
  try {
    return JSON.parse(sh(`git show ${ref}:dados_versao.json`)).site || '';
  } catch {
    return null;
  }
};
const antes = siteQuente(base);
const depois = siteQuente('HEAD');
if (antes === null || depois === null || antes !== depois) {
  // Custo (dono do site, 25/11/2026: teto de US$ 20-30/mês na Vercel): mudança SÓ de dados publica no
  // máximo a cada 30 min (antes: a cada ~8 min, 100+ publicações por dia). Código/página publica na hora (acima).
  if (temBase) {
    const quando = (ref) => Number(sh(`git show -s --format=%ct ${ref}`).trim());
    const passou = quando('HEAD') - quando(base);
    if (passou < INTERVALO_MIN * 60) {
      console.log(`Notícias novas, mas a última publicação foi há ${Math.round(passou / 60)} min: espera até ${INTERVALO_MIN} min (custo).`);
      process.exit(0);
    }
  }
  process.exit(1);
}

console.log('Só dados de anos antigos, cursores ou juiz mudaram: publicação fica para a próxima rodada da parte quente.');
process.exit(0);
