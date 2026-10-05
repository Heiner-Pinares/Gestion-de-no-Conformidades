document.addEventListener("DOMContentLoaded", () => {
  const modal = document.querySelector("[data-follow-modal]");
  const form = document.querySelector("[data-follow-form]");
  if (!form) return;

  const number = form.querySelector('[name="porcentaje_avance"]');
  const range = form.querySelector("[data-follow-range]");
  const comment = form.querySelector('[name="comentario"]');
  const count = form.querySelector("[data-follow-count]");
  const file = form.querySelector('[name="archivo"]');
  const fileRow = form.querySelector("[data-follow-file-row]");
  const fileName = form.querySelector("[data-follow-file-name]");
  const fileSize = form.querySelector("[data-follow-file-size]");
  const drop = form.querySelector("[data-follow-drop]");
  let trigger = null;

  const localDateTime = () => {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  };
  const updateCount = () => { if (count) count.textContent = String((comment?.value || "").length); };
  const syncFromNumber = () => {
    if (!number || !range) return;
    const value = Math.max(Number(number.min || 0), Math.min(100, Number(number.value || 0)));
    number.value = String(value);
    range.value = String(value);
  };
  const showFile = () => {
    const selected = file?.files?.[0];
    if (!fileRow) return;
    fileRow.hidden = !selected;
    if (!selected) return;
    fileName.textContent = selected.name;
    fileSize.textContent = selected.size < 1048576 ? `${Math.ceil(selected.size / 1024)} KB` : `${(selected.size / 1048576).toFixed(1)} MB`;
  };
  const clearFile = () => { if (file) file.value = ""; showFile(); };

  number?.addEventListener("input", syncFromNumber);
  range?.addEventListener("input", () => { number.value = range.value; });
  comment?.addEventListener("input", updateCount);
  file?.addEventListener("change", showFile);
  form.querySelector("[data-follow-file-remove]")?.addEventListener("click", clearFile);
  ["dragenter", "dragover"].forEach((name) => drop?.addEventListener(name, (event) => { event.preventDefault(); drop.classList.add("dragging"); }));
  ["dragleave", "drop"].forEach((name) => drop?.addEventListener(name, (event) => { event.preventDefault(); drop.classList.remove("dragging"); }));
  drop?.addEventListener("drop", (event) => {
    if (event.dataTransfer.files.length && file) {
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      file.files = transfer.files;
      showFile();
    }
  });

  const close = () => {
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("follow-modal-open");
    trigger?.focus();
  };
  const fill = (button) => {
    trigger = button;
    const data = button.dataset;
    form.action = data.actionUrl;
    form.querySelector("[data-follow-code]").textContent = data.code;
    form.querySelector("[data-follow-responsable]").textContent = data.responsable;
    form.querySelector("[data-follow-estado]").textContent = data.estado;
    form.querySelector("[data-follow-current]").textContent = data.avance;
    form.querySelector("[data-follow-current-bar]").value = Number(data.avance);
    form.querySelector("[data-follow-fet]").textContent = data.fet;
    number.min = data.avance;
    number.value = data.avance;
    range.min = data.avance;
    range.value = data.avance;
    comment.value = "";
    const date = form.querySelector("[data-follow-date]");
    if (date) date.value = localDateTime();
    clearFile();
    updateCount();
  };

  document.querySelectorAll("[data-follow-open]").forEach((button) => button.addEventListener("click", () => {
    fill(button);
    modal.hidden = false;
    document.body.classList.add("follow-modal-open");
    number.focus();
  }));
  form.querySelectorAll("[data-follow-close]").forEach((button) => button.addEventListener("click", close));
  modal?.addEventListener("click", (event) => { if (event.target === modal) close(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && modal && !modal.hidden) close(); });

  syncFromNumber();
  updateCount();
  showFile();

  const reprogramModal = document.querySelector("[data-reprogram-modal]");
  const reprogramForm = document.querySelector("[data-reprogram-form]");
  if (reprogramModal && reprogramForm) {
    const reason = reprogramForm.querySelector('[name="motivo"]');
    const reasonCount = reprogramForm.querySelector("[data-reprogram-count]");
    const reprogramFile = reprogramForm.querySelector('[name="archivo"]');
    const reprogramFileRow = reprogramForm.querySelector("[data-reprogram-file-row]");
    const reprogramDrop = reprogramForm.querySelector("[data-reprogram-drop]");
    let reprogramTrigger = null;
    const updateReasonCount = () => { reasonCount.textContent = String((reason.value || "").length); };
    const showReprogramFile = () => {
      const selected = reprogramFile.files?.[0];
      reprogramFileRow.hidden = !selected;
      if (!selected) return;
      reprogramForm.querySelector("[data-reprogram-file-name]").textContent = selected.name;
      reprogramForm.querySelector("[data-reprogram-file-size]").textContent = selected.size < 1048576 ? `${Math.ceil(selected.size / 1024)} KB` : `${(selected.size / 1048576).toFixed(1)} MB`;
    };
    const clearReprogramFile = () => { reprogramFile.value = ""; showReprogramFile(); };
    const closeReprogram = (event) => {
      event?.preventDefault();
      reprogramModal.hidden = true;
      document.body.classList.remove("follow-modal-open");
      reprogramTrigger?.focus();
    };
    document.querySelectorAll("[data-reprogram-open]").forEach((button) => button.addEventListener("click", (event) => {
      event.preventDefault();
      reprogramTrigger = button;
      reprogramForm.action = button.dataset.actionUrl;
      reprogramForm.querySelector("[data-reprogram-code]").textContent = button.dataset.code;
      reprogramForm.querySelector("[data-reprogram-description]").textContent = button.dataset.description;
      reprogramForm.querySelector("[data-reprogram-owner]").textContent = button.dataset.owner;
      reprogramForm.querySelector("[data-reprogram-current]").textContent = button.dataset.current;
      reprogramForm.querySelector('[name="nueva_fecha"]').value = "";
      reprogramForm.querySelector('[name="aprobador"]').value = "";
      reason.value = "";
      clearReprogramFile();
      updateReasonCount();
      reprogramModal.hidden = false;
      document.body.classList.add("follow-modal-open");
      reprogramForm.querySelector('[name="nueva_fecha"]').focus();
    }));
    reprogramForm.querySelectorAll("[data-reprogram-close]").forEach((button) => button.addEventListener("click", closeReprogram));
    reason.addEventListener("input", updateReasonCount);
    reprogramFile.addEventListener("change", showReprogramFile);
    reprogramForm.querySelector("[data-reprogram-file-remove]")?.addEventListener("click", clearReprogramFile);
    ["dragenter", "dragover"].forEach((name) => reprogramDrop.addEventListener(name, (event) => { event.preventDefault(); reprogramDrop.classList.add("dragging"); }));
    ["dragleave", "drop"].forEach((name) => reprogramDrop.addEventListener(name, (event) => { event.preventDefault(); reprogramDrop.classList.remove("dragging"); }));
    reprogramDrop.addEventListener("drop", (event) => {
      if (event.dataTransfer.files.length) {
        const transfer = new DataTransfer();
        transfer.items.add(event.dataTransfer.files[0]);
        reprogramFile.files = transfer.files;
        showReprogramFile();
      }
    });
    reprogramModal.addEventListener("click", (event) => { if (event.target === reprogramModal) closeReprogram(); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !reprogramModal.hidden) closeReprogram(); });
  }

  const historyModal = document.querySelector("[data-history-modal]");
  if (historyModal) {
    let historyTrigger = null;
    const closeHistory = (event) => {
      historyModal.hidden = true;
      document.body.classList.remove("follow-modal-open");
      if (event?.currentTarget?.tagName !== "A") event?.preventDefault();
      historyTrigger?.focus();
    };
    const setText = (selector, value) => {
      const element = historyModal.querySelector(selector);
      if (element) element.textContent = value || "—";
    };
    document.querySelectorAll("[data-history-open]").forEach((button) => button.addEventListener("click", () => {
      historyTrigger = button;
      setText("[data-history-type]", button.dataset.historyType);
      setText("[data-history-date]", button.dataset.historyDate);
      setText("[data-history-user]", button.dataset.historyUser);
      setText("[data-history-progress]", button.dataset.historyProgress);
      setText("[data-history-change]", button.dataset.historyChange);
      setText("[data-history-comment]", button.dataset.historyComment);
      const evidenceList = historyModal.querySelector("[data-history-evidence-list]");
      const evidenceTemplate = document.querySelector(
        `[data-history-evidence-template="${button.dataset.historyEvidenceKey}"]`
      );
      evidenceList.replaceChildren(
        evidenceTemplate
          ? evidenceTemplate.content.cloneNode(true)
          : Object.assign(document.createElement("p"), {
              className: "history-evidence-empty",
              textContent: "Este movimiento no tiene documentos adjuntos.",
            })
      );
      const isReprogram = button.dataset.historyType === "Reprogramación";
      historyModal.querySelector("[data-history-progress-row]").hidden = isReprogram;
      historyModal.querySelector("[data-history-change-row]").hidden = !isReprogram;
      historyModal.hidden = false;
      document.body.classList.add("follow-modal-open");
      historyModal.querySelector("[data-history-close]")?.focus();
    }));
    historyModal.querySelectorAll("[data-history-close]").forEach((button) => button.addEventListener("click", closeHistory));
    historyModal.addEventListener("click", (event) => { if (event.target === historyModal) closeHistory(event); });
    document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !historyModal.hidden) closeHistory(event); });
  }
});
