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
