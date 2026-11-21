// Visitantes (pedido do dono do site, 21/11/2026): país, estado e cidade aproximados de cada visitante
// (uma vez por dia por navegador; dados de localização que a Vercel deduz do endereço de internet).
// Não guarda IP nem nada que identifique a pessoa. Grava direto no repositório PRIVADO
// 7773333123/radar-visitas (visitas/AAAA-MM-DD.jsonl): nada aparece no site nem no repositório público.
// Precisa da variável GH_VISITA_TOKEN na Vercel (token do GitHub com acesso a radar-visitas, Contents: write).
const PRIVADO = '7773333123/radar-visitas';
const ROBO = /bot|crawl|spider|slurp|facebookexternalhit|whatsapp|preview|headless|lighthouse|monitor/i;

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
  if (req.method !== 'POST' || !token || (!teste && ROBO.test(req.headers['user-agent'] || ''))) {
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
