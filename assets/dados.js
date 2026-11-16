/* Dados abertos: arquivos para download e dicionário de dados. */
import { $, esc, num, carregarFeed, iniciarCabecalho } from './core.js';

const ARQUIVOS = [
  { arq: 'dados/noticias.csv', fmt: 'CSV', titulo: 'Notícias do acervo', desc: 'Uma linha por notícia, sem duplicatas: data, título, fonte, estado, tipos, órgãos, rodovia, quantidades e link.' },
  { arq: 'dados/mensal_por_uf.csv', fmt: 'CSV', titulo: 'Série mensal por estado', desc: 'Notícias e quantidades somadas por mês e estado, prontas para gráficos e planilhas.' },
  { arq: 'dados/dicionario.json', fmt: 'JSON', titulo: 'Dicionário de dados', desc: 'Descrição de cada campo, unidades, licença e avisos de uso.' },
  { arq: 'feed.json', fmt: 'JSON', titulo: 'Feed completo (desenvolvedores)', desc: 'O mesmo arquivo que alimenta o site, com chaves curtas. Ideal para integrações.' },
];

async function tamanho(arq) {
  try {
    const r = await fetch(arq, { method: 'HEAD' });
    const b = Number(r.headers.get('content-length') || 0);
    return b ? (b > 1e6 ? `${num(b / 1e6, 1)} MB` : `${num(b / 1e3)} KB`) : '';
  } catch { return ''; }
}

async function iniciar() {
  const promessa = carregarFeed();
  iniciarCabecalho(promessa);
  $('downloads').innerHTML = ARQUIVOS.map((a, k) =>
    `<div class="dl"><span class="fmt">${a.fmt}</span><h3>${esc(a.titulo)}</h3><p>${esc(a.desc)}</p>` +
    `<p class="note" id="tam${k}"></p><a class="btn" href="${a.arq}" download>Baixar</a></div>`).join('');
  ARQUIVOS.forEach((a, k) => tamanho(a.arq).then((t) => { if (t) $(`tam${k}`).textContent = t; }));
  promessa.then((ctx) => {
    $('tam0').textContent = `${num(ctx.noticias.length)} notícias${$('tam0').textContent ? ' · ' + $('tam0').textContent : ''}`;
    const hoje = new Date().toLocaleDateString('pt-BR');
    $('citacao').textContent = `Radar das Apreensões. Banco de notícias de apreensões no Brasil. Disponível em: https://www.radardasapreensoes.com.br/dados. Acesso em: ${hoje}.`;
  }).catch(() => {});
  try {
    const d = await (await fetch('dados/dicionario.json')).json();
    $('dicionario').innerHTML = `<table class="dict"><thead><tr><th>Campo</th><th>Descrição</th></tr></thead><tbody>` +
      Object.entries(d.campos).map(([k, v]) => `<tr><td><code>${esc(k)}</code></td><td>${esc(v)}</td></tr>`).join('') +
      `</tbody></table><p class="note">${esc(d.aviso || '')}</p>`;
  } catch { $('dicionario').innerHTML = '<p class="note">Dicionário indisponível no momento.</p>'; }
}
iniciar();
