(() => {
  const button = document.querySelector('[data-admin-sidebar-toggle]');
  if (button) {
    button.addEventListener('click', () => {
      const collapsed = document.body.classList.toggle('admin-sidebar-collapsed');
      button.setAttribute('aria-expanded', String(!collapsed));
      button.setAttribute('aria-label', collapsed ? 'Expandir menú' : 'Contraer menú');
      button.textContent = collapsed ? '»' : '«';
    });
  }

  const dialog = document.querySelector('[data-delete-dialog]');
  if (!dialog) return;
  const form = dialog.querySelector('[data-delete-form]');
  const code = dialog.querySelector('[data-delete-code]');
  const title = dialog.querySelector('[data-delete-title]');
  const confirmation = dialog.querySelector('[data-delete-confirmation]');
  const cancel = dialog.querySelector('[data-delete-cancel]');

  document.querySelectorAll('[data-delete-open]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      form.action = trigger.dataset.deleteUrl;
      code.textContent = trigger.dataset.deleteCode;
      title.textContent = trigger.dataset.deleteTitle ? ` (${trigger.dataset.deleteTitle})` : '';
      confirmation.value = trigger.dataset.deleteCode;
      dialog.showModal();
      cancel.focus();
    });
  });
  cancel.addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
})();
