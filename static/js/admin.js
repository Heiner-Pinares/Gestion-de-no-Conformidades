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
  if (dialog) {
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
  }

  const catalogDialog = document.querySelector('[data-catalog-delete-dialog]');
  if (catalogDialog) {
    const catalogForm = catalogDialog.querySelector('[data-catalog-delete-form]');
    const catalogName = catalogDialog.querySelector('[data-catalog-delete-name]');
    const catalogCancel = catalogDialog.querySelector('[data-catalog-delete-cancel]');
    document.querySelectorAll('[data-catalog-delete-open]').forEach((trigger) => {
      trigger.addEventListener('click', () => {
        catalogForm.action = trigger.dataset.deleteUrl;
        catalogName.textContent = trigger.dataset.deleteName;
        catalogDialog.showModal();
        catalogCancel.focus();
      });
    });
    catalogCancel.addEventListener('click', () => catalogDialog.close());
    catalogDialog.addEventListener('click', (event) => {
      if (event.target === catalogDialog) catalogDialog.close();
    });
  }

  const bulkForm = document.querySelector('[data-bulk-delete-form]');
  const bulkDialog = document.querySelector('[data-bulk-delete-dialog]');
  if (!bulkForm || !bulkDialog) return;
  const selectAll = bulkForm.querySelector('[data-bulk-select-all]');
  const selections = [...bulkForm.querySelectorAll('[data-bulk-select]')];
  const openBulkDialog = bulkForm.querySelector('[data-bulk-delete-open]');
  const summary = bulkForm.querySelector('[data-bulk-selection-summary]');
  const bulkCount = bulkDialog.querySelector('[data-bulk-delete-count]');
  const bulkCodes = bulkDialog.querySelector('[data-bulk-delete-codes]');
  const cancelBulk = bulkDialog.querySelector('[data-bulk-delete-cancel]');

  const selectedItems = () => selections.filter((checkbox) => checkbox.checked);
  const updateBulkSelection = () => {
    const selected = selectedItems();
    const count = selected.length;
    openBulkDialog.disabled = count === 0;
    summary.textContent = count
      ? `${count} ${count === 1 ? 'hallazgo seleccionado' : 'hallazgos seleccionados'}.`
      : 'Selecciona los hallazgos que deseas eliminar.';
    if (selectAll) {
      selectAll.checked = selections.length > 0 && count === selections.length;
      selectAll.indeterminate = count > 0 && count < selections.length;
    }
    selections.forEach((checkbox) => {
      checkbox.closest('tr')?.classList.toggle('is-selected', checkbox.checked);
    });
  };

  selectAll?.addEventListener('change', () => {
    selections.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
    updateBulkSelection();
  });
  selections.forEach((checkbox) => checkbox.addEventListener('change', updateBulkSelection));
  openBulkDialog.addEventListener('click', () => {
    const selected = selectedItems();
    if (!selected.length) return;
    const codes = selected.map((checkbox) => checkbox.dataset.code);
    bulkCount.textContent = `${selected.length} ${selected.length === 1 ? 'hallazgo' : 'hallazgos'}`;
    bulkCodes.textContent = codes.length > 5
      ? `${codes.slice(0, 5).join(', ')} y ${codes.length - 5} más.`
      : `${codes.join(', ')}.`;
    bulkDialog.showModal();
    cancelBulk.focus();
  });
  cancelBulk.addEventListener('click', () => bulkDialog.close());
  bulkDialog.addEventListener('click', (event) => {
    if (event.target === bulkDialog) bulkDialog.close();
  });
  bulkForm.addEventListener('submit', (event) => {
    if (!selectedItems().length) event.preventDefault();
  });
  updateBulkSelection();
})();
