/* Páginas próprias (notícia, estado, tipo, relatório, institucionais): tema e busca. */
const raiz = document.documentElement;
try { const t = localStorage.getItem('tema'); if (t) raiz.dataset.theme = t; } catch { /* armazenamento indisponível */ }
document.getElementById('tema')?.addEventListener('click', () => {
  const escuro = (raiz.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark';
  raiz.dataset.theme = escuro ? 'light' : 'dark';
  try { localStorage.setItem('tema', raiz.dataset.theme); } catch { /* ignore */ }
});
// Foto da fonte que não carrega: some, sem deixar ícone quebrado.
document.addEventListener('error', (e) => {
  if (e.target instanceof HTMLImageElement) (e.target.closest('.media') || e.target).remove();
}, true);
// Miniatura buscada na hora (/api/foto) que não existe: some, sem deixar caixa vazia.
document.addEventListener('error', (e) => {
  const img = e.target;
  if (img instanceof HTMLImageElement && img.hasAttribute('data-ph')) img.closest('.media')?.remove();
}, true);

// Barra de compartilhamento: copiar link e menu do sistema (WhatsApp é um link direto).
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-copiar], [data-compartilhar]');
  if (!b) return;
  const link = b.dataset.copiar || b.dataset.compartilhar;
  try {
    if (b.dataset.compartilhar && navigator.share) { await navigator.share({ title: b.dataset.titulo || document.title, url: link }); return; }
    await navigator.clipboard.writeText(link);
    const antes = b.textContent; b.textContent = 'Link copiado ✓'; setTimeout(() => { b.textContent = antes; }, 2000);
  } catch { /* cancelado */ }
});
