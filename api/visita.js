// Primeira visita (pedido do dono do site, 21/11/2026): registra UMA vez país, estado e cidade
// aproximados do primeiro visitante (dados de localização que a Vercel deduz do endereço de internet).
// Não guarda IP nem nada que identifique a pessoa. Envia ao GitHub (repository_dispatch) e o
// workflow visita.yml grava primeira_visita.json, que o Claude lê e informa ao dono.
// Precisa da variável GH_VISITA_TOKEN na Vercel (token do GitHub só deste repositório, Contents: write).
const REPO = '7773333123/radar-das-apreensoes';
const ROBO = /bot|crawl|spider|slurp|facebookexternalhit|whatsapp|preview|headless|lighthouse|monitor/i;

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const token = process.env.GH_VISITA_TOKEN;
  if (/[?&]teste=1\b/.test(req.url || '') && req.method === 'POST') {
    // Diagnóstico: diz se a chave existe e o que o GitHub responde (sem mostrar a chave).
    let github = 0, msg = '';
    if (token) {
      try {
        const r = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'User-Agent': 'radar-visita' },
          body: JSON.stringify({ event_type: 'teste-visita', client_payload: { pais: 'teste' } }),
          signal: AbortSignal.timeout(5000),
        });
        github = r.status;
        msg = r.ok ? '' : (await r.text()).slice(0, 200);
      } catch (e) { msg = String(e).slice(0, 200); }
    }
    res.setHeader('Content-Type', 'application/json');
    return res.end(JSON.stringify({ chave_configurada: Boolean(token), github, msg }));
  }
  if (req.method !== 'POST' || !token || ROBO.test(req.headers['user-agent'] || '')) {
    res.statusCode = 204;
    return res.end();
  }
  // Teste (?teste=1): confere a chave sem registrar a primeira visita.
  const teste = /[?&]teste=1\b/.test(req.url || '');
  // Já registrada? (o arquivo fica no repositório, não no site)
  if (!teste) try {
    const r = await fetch(`https://raw.githubusercontent.com/${REPO}/main/primeira_visita.json`, { method: 'HEAD', signal: AbortSignal.timeout(3000) });
    if (r.ok) { res.statusCode = 204; return res.end(); }
  } catch { /* segue */ }
  const h = (k) => { try { return decodeURIComponent(req.headers[k] || ''); } catch { return req.headers[k] || ''; } };
  const codigo = h('x-vercel-ip-country');
  let pais = codigo;
  try { pais = new Intl.DisplayNames(['pt-BR'], { type: 'region' }).of(codigo) || codigo; } catch { /* código */ }
  const visita = { pais, codigo_pais: codigo, estado: h('x-vercel-ip-country-region'), cidade: h('x-vercel-ip-city'),
    quando: new Date().toISOString().slice(0, 16) + 'Z' };
  try {
    await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'User-Agent': 'radar-visita' },
      body: JSON.stringify({ event_type: teste ? 'teste-visita' : 'primeira-visita', client_payload: visita }),
      signal: AbortSignal.timeout(5000),
    });
  } catch { /* sem registro */ }
  res.statusCode = 204;
  res.end();
};
