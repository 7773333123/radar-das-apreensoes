// Visitantes (pedido do dono do site, 21/11/2026): país, estado e cidade aproximados de cada visitante
// (uma vez por dia por navegador; dados de localização que a Vercel deduz do endereço de internet).
// Desde 24/11/2026 cada linha diz se é pessoa, robô (com o nome: Google, Bing, WhatsApp...) ou
// provável robô (navegador comum saindo de centro de dados), e o tipo de navegador/aparelho.
// Não guarda IP nem nada que identifique a pessoa. Grava direto no repositório PRIVADO
// 7773333123/radar-visitas (visitas/AAAA-MM-DD.jsonl): nada aparece no site nem no repositório público.
// Precisa da variável GH_VISITA_TOKEN na Vercel (token do GitHub com acesso a radar-visitas, Contents: write).
const PRIVADO = '7773333123/radar-visitas';
const ROBO = /bot|crawl|spider|slurp|facebookexternalhit|whatsapp|preview|headless|lighthouse|monitor/i;
// Robôs conhecidos pelo nome que o navegador envia (24/11/2026: o dono quer saber quem é cada robô).
// A ordem importa: os mais específicos primeiro.
const ROBOS = [
  ['Google-InspectionTool', 'Google (inspeção do Search Console)'], ['AdsBot-Google', 'Google Ads'],
  ['Mediapartners-Google', 'Google AdSense'], ['Storebot-Google', 'Google Shopping'], ['GoogleOther', 'Google (outros usos)'],
  ['Google-Extended', 'Google (IA)'], ['Googlebot', 'Google (busca)'], ['bingbot', 'Bing (busca)'], ['BingPreview', 'Bing (prévia)'],
  ['YandexBot', 'Yandex'], ['Baiduspider', 'Baidu'], ['DuckDuckBot', 'DuckDuckGo'], ['Applebot', 'Apple (Siri/Spotlight)'],
  ['facebookexternalhit', 'Facebook/Instagram (prévia de link)'], ['meta-externalagent', 'Meta (IA)'],
  ['WhatsApp', 'WhatsApp (prévia de link)'], ['TelegramBot', 'Telegram (prévia de link)'], ['Twitterbot', 'X/Twitter (prévia de link)'],
  ['LinkedInBot', 'LinkedIn (prévia de link)'], ['Discordbot', 'Discord (prévia de link)'], ['Slackbot', 'Slack (prévia de link)'],
  ['OAI-SearchBot', 'OpenAI (busca do ChatGPT)'], ['ChatGPT-User', 'ChatGPT (a pedido de usuário)'], ['GPTBot', 'OpenAI (treino de IA)'],
  ['Claude-User', 'Claude (a pedido de usuário)'], ['ClaudeBot', 'Anthropic (IA)'], ['PerplexityBot', 'Perplexity (IA)'],
  ['Bytespider', 'ByteDance/TikTok (IA)'], ['Amazonbot', 'Amazon'], ['AhrefsBot', 'Ahrefs (SEO)'], ['SemrushBot', 'Semrush (SEO)'],
  ['MJ12bot', 'Majestic (SEO)'], ['DotBot', 'Moz (SEO)'], ['PetalBot', 'Huawei Petal'], ['Chrome-Lighthouse', 'Lighthouse (teste de velocidade)'],
  ['HeadlessChrome', 'Chrome automatizado (sem tela)'], ['python-requests', 'script Python'], ['curl', 'curl'],
];
// Cidades de grandes centros de dados (Google, Amazon, Microsoft): acesso daí quase sempre é máquina.
const CENTRO_DE_DADOS = new Set(['Oklahoma City/OK', 'Pryor/OK', 'Council Bluffs/IA', 'The Dalles/OR', 'Boardman/OR', 'Ashburn/VA',
  'Moncks Corner/SC', 'Quincy/WA', 'Lenoir/NC', 'Douglas County/GA', 'Mayes County/OK', 'Santa Clara/CA', 'San Jose/CA',
  'Des Moines/IA', 'Columbus/OH', 'Dublin/OH', 'Hillsboro/OR', 'Boydton/VA', 'San Antonio/TX', 'Cheyenne/WY']);

function nomeRobo(ua) {
  const r = ROBOS.find(([k]) => ua.toLowerCase().includes(k.toLowerCase()));
  if (r) return r[1];
  return ROBO.test(ua) || !ua ? 'robô não identificado' : '';
}
// Só o tipo de navegador e de aparelho (nada que identifique a pessoa).
function navegador(ua) {
  const so = /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iPhone/iPad' : /Windows/.test(ua) ? 'Windows'
    : /Mac OS X/.test(ua) ? 'Mac' : /CrOS/.test(ua) ? 'Chromebook' : /Linux/.test(ua) ? 'Linux' : 'outro';
  const m = ua.match(/(Edg|OPR|SamsungBrowser|Firefox|CriOS|Chrome|Version(?=\/[\d.]+ .*Safari))\/(\d+)/);
  const nome = m ? ({ Edg: 'Edge', OPR: 'Opera', SamsungBrowser: 'Samsung', CriOS: 'Chrome', Version: 'Safari' }[m[1]] || m[1]) + ' ' + m[2] : 'outro';
  return `${nome} · ${so}`;
}

async function acrescentar(token, caminho, linha, mensagem) {
  const url = `https://api.github.com/repos/${PRIVADO}/contents/${caminho}`;
  const headers = { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'User-Agent': 'radar-visita' };
  let status = 0;
  for (let t = 0; t < 4; t++) {  // dois visitantes ao mesmo tempo: o segundo relê e tenta de novo
    const g = await fetch(url, { headers, signal: AbortSignal.timeout(5000) });
    let sha, atual = '';
    if (g.ok) { const j = await g.json(); sha = j.sha; atual = Buffer.from(j.content || '', 'base64').toString('utf8'); }
    const p = await fetch(url, { method: 'PUT', headers, signal: AbortSignal.timeout(5000),
      body: JSON.stringify({ message: mensagem, content: Buffer.from(atual + linha).toString('base64'), ...(sha ? { sha } : {}) }) });
    status = p.status;
    if (p.ok || (p.status !== 409 && p.status !== 422)) return status;
  }
  return status;
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const token = process.env.GH_VISITA_TOKEN;
  const teste = /[?&]teste=1\b/.test(req.url || '');
  if (req.method !== 'POST' || !token) {
    res.statusCode = 204;
    return res.end();
  }
  const h = (k) => { try { return decodeURIComponent(req.headers[k] || ''); } catch { return req.headers[k] || ''; } };
  const codigo = h('x-vercel-ip-country');
  let pais = codigo;
  try { pais = new Intl.DisplayNames(['pt-BR'], { type: 'region' }).of(codigo) || codigo; } catch { /* código */ }
  const agora = new Date();
  const visita = { pais, codigo_pais: codigo, estado: h('x-vercel-ip-country-region'), cidade: h('x-vercel-ip-city'),
    quando: agora.toISOString().slice(0, 16) + 'Z' };
  // Robô ou pessoa (24/11/2026): robôs também ficam registrados, com o nome, para o dono saber quem lê o site.
  const ua = String(req.headers['user-agent'] || '').slice(0, 400);
  const robo = nomeRobo(ua);
  if (robo) { visita.tipo = 'robo'; visita.robo = robo; } else {
    visita.tipo = 'pessoa';
    visita.navegador = navegador(ua);
    if (CENTRO_DE_DADOS.has(`${visita.cidade}/${visita.estado}`) && visita.codigo_pais === 'US') {
      visita.tipo = 'provavel_robo';  // navegador comum, mas saindo de centro de dados
    }
  }
  const dia = new Date(agora.getTime() - 3 * 3600e3).toISOString().slice(0, 10);  // dia em Brasília
  let status = 0;
  try {
    status = teste
      ? await acrescentar(token, 'teste/ok.txt', `teste ${visita.quando}\n`, 'Teste da gravação')
      : await acrescentar(token, `visitas/${dia}.jsonl`, JSON.stringify(visita) + '\n', `Visitante ${visita.quando}`);
  } catch (e) { status = -1; }
  if (teste) {
    res.setHeader('Content-Type', 'application/json');
    return res.end(JSON.stringify({ chave_configurada: true, gravacao_privada: status }));
  }
  res.statusCode = 204;
  res.end();
};
