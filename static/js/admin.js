(() => {
  const button = document.querySelector('[data-admin-sidebar-toggle]');
  if (!button) return;
  button.addEventListener('click', () => {
    const collapsed = document.body.classList.toggle('admin-sidebar-collapsed');
    button.setAttribute('aria-expanded', String(!collapsed));
    button.setAttribute('aria-label', collapsed ? 'Expandir menú' : 'Contraer menú');
    button.textContent = collapsed ? '»' : '«';
  });
})();
