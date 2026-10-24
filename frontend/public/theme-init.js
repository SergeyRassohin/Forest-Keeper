// Apply only a validated presentation preference before the first paint.
(() => {
  let saved;
  try { saved = localStorage.getItem('fk-theme'); } catch { /* Storage can be blocked. */ }
  const theme = saved === 'light' || saved === 'dark' ? saved
    : window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = theme;
})();
