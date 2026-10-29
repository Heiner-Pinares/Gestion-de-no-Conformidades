document.addEventListener("DOMContentLoaded", () => {
  const modal = document.querySelector("[data-efficacy-modal]");
  const success = document.querySelector("[data-efficacy-success]");
  const form = document.querySelector("[data-efficacy-form]");
  const openButton = document.querySelector("[data-efficacy-open]");
  let trigger = null;

  const syncBody = () => {
    const open = (modal && !modal.hidden) || (success && !success.hidden);
    document.body.classList.toggle("efficacy-modal-open", Boolean(open));
  };
  const closeModal = () => {
    if (!modal) return;
    modal.hidden = true;
    syncBody();
    trigger?.focus();
  };
  const openModal = () => {
    if (!modal) return;
    trigger = openButton;
    modal.hidden = false;
    syncBody();
    form?.querySelector('[name="fecha_evaluacion"]')?.focus();
  };
  const closeSuccess = () => {
    if (!success) return;
    success.hidden = true;
    syncBody();
    const url = new URL(window.location.href);
    url.searchParams.delete("evaluacion_enviada");
    window.history.replaceState({}, "", url);
  };

  openButton?.addEventListener("click", openModal);
  modal?.querySelectorAll("[data-efficacy-close]").forEach((button) => button.addEventListener("click", closeModal));
  modal?.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
  success?.querySelectorAll("[data-efficacy-success-close]").forEach((button) => button.addEventListener("click", closeSuccess));
  success?.addEventListener("click", (event) => { if (event.target === success) closeSuccess(); });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (success && !success.hidden) closeSuccess();
    else if (modal && !modal.hidden) closeModal();
  });

  const input = form?.querySelector('[name="archivo"]');
  const drop = form?.querySelector("[data-efficacy-drop]");
  const fileRow = form?.querySelector("[data-efficacy-file]");
  const showFile = () => {
    const file = input?.files?.[0];
    if (!fileRow) return;
    fileRow.hidden = !file;
    if (!file) return;
    fileRow.querySelector("[data-efficacy-file-name]").textContent = file.name;
    fileRow.querySelector("[data-efficacy-file-size]").textContent = file.size < 1048576
      ? `${Math.ceil(file.size / 1024)} KB`
      : `${(file.size / 1048576).toFixed(1)} MB`;
  };
  input?.addEventListener("change", showFile);
  form?.querySelector("[data-efficacy-file-remove]")?.addEventListener("click", () => {
    input.value = "";
    showFile();
  });
  ["dragenter", "dragover"].forEach((name) => drop?.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((name) => drop?.addEventListener(name, (event) => {
    event.preventDefault();
    drop.classList.remove("is-dragging");
  }));
  drop?.addEventListener("drop", (event) => {
    const file = event.dataTransfer?.files?.[0];
    if (!file || !input) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    showFile();
  });

  syncBody();
});
