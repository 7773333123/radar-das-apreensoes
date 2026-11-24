// Robô bloqueado (24/11/2026): o Bytespider (ByteDance/TikTok) coleta o site em massa para treinar IA e
// ignora o robots.txt. vercel.json redireciona qualquer acesso dele para cá: resposta mínima, sem custo.
module.exports = (req, res) => {
  res.statusCode = 403;
  res.setHeader('Cache-Control', 'public, max-age=86400, s-maxage=86400');
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.end('Acesso bloqueado para este robô.');
};
