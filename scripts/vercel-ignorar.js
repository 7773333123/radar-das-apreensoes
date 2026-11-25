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
// Publica quando: branch main E mudou algum arquivo que não é dado/cursor (código, página, regra).
// Desde 25/11/2026 os dados vão para o GitHub Pages (publicar_dados.yml) e o site os lê de lá; mudança só de
// dados não publica na Vercel. Na dúvida (sem histórico para comparar), publica.
const { execSync } = require('child_process');

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
const SO_DADOS = /^(dados_versao|capas_ia|revisao_titulos|videos_oficiais|youtube_canais|marcas_dagua|duplicatas_suspeitas|feeds_saude|buscadores_cursor|cobertura_historica|agencia_cursor|historico_cursor|juiz_[a-z_]+|wayback_cursor_\d{4}|[a-z_]*_cursor(_\d{4})?)\.json$/;

let arquivos;
try {
  arquivos = sh(`git diff --name-only ${base} HEAD`).split('\n').filter(Boolean);
} catch {
  process.exit(1);
}
if (arquivos.some((f) => !SO_DADOS.test(f))) process.exit(1); // código, página ou regra mudou

// Só dados mudaram: as notícias já vão para o GitHub Pages (publicar_dados.yml), de onde o site as lê.
// A Vercel não publica (custo, 25/11/2026: só o plano, sem gasto extra).
console.log('Só dados mudaram: vão para o GitHub Pages; a Vercel não publica.');
process.exit(0);
