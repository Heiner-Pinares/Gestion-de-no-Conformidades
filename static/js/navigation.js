(() => {
  const storageKey = 'portalNcNavigationHistory';
  if (document.body.dataset.portalAuthenticated !== 'true') {
    window.sessionStorage.removeItem(storageKey);
    return;
  }

  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  let navigationHistory = [];
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(storageKey) || '[]');
    navigationHistory = Array.isArray(stored)
      ? stored.filter((entry) => typeof entry === 'string' && entry.startsWith('/'))
      : [];
  } catch (_error) {
    navigationHistory = [];
  }
  if (navigationHistory[navigationHistory.length - 1] !== current) {
    navigationHistory.push(current);
    navigationHistory = navigationHistory.slice(-30);
    window.sessionStorage.setItem(storageKey, JSON.stringify(navigationHistory));
  }

  document.querySelectorAll('[data-history-back]').forEach((button) => {
    button.addEventListener('click', () => {
      const fallback = button.dataset.fallback || '/';
      const history = [...navigationHistory];
      if (history[history.length - 1] === current) history.pop();
      const previous = history.pop();
      window.sessionStorage.setItem(storageKey, JSON.stringify(history));
      window.location.assign(previous || fallback);
    });
  });
})();
