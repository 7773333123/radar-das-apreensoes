/* Medição de compartilhamentos (Vercel Web Analytics, sem cookies e sem dados pessoais):
   - cliques em "Enviar no WhatsApp", "Copiar link" e "Compartilhar" (evento "Compartilhamento");
   - visitas que chegaram por um link compartilhado (evento "Visita por compartilhamento"). */
window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
export function evento(name, data) {
  try { window.va('event', { name, data }); } catch { /* sem medição */ }
}
// Link compartilhado com a origem marcada (removida da barra de endereço na chegada).
export const comOrigem = (link, origem) => `${link}${link.includes('?') ? '&' : '?'}utm_source=${origem}&utm_medium=compartilhamento`;

document.addEventListener('click', (e) => {
  const b = e.target.closest?.('.share-wa, [data-copiar], [data-compartilhar]');
  if (!b) return;
  const canal = b.classList.contains('share-wa') ? 'WhatsApp' : b.hasAttribute('data-copiar') ? 'Copiar link' : 'Compartilhar';
  evento('Compartilhamento', { canal, pagina: location.pathname.slice(0, 120) });
}, true);

const p = new URLSearchParams(location.search);
if (p.get('utm_medium') === 'compartilhamento') {
  evento('Visita por compartilhamento', { origem: p.get('utm_source') || 'desconhecida', pagina: location.pathname.slice(0, 120) });
  p.delete('utm_source');
  p.delete('utm_medium');
  history.replaceState(history.state, '', location.pathname + (p.toString() ? `?${p}` : '') + location.hash);
}
