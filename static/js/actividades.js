document.addEventListener("DOMContentLoaded", () => {
  const plan = document.querySelector("[data-activity-plan]");
  if (plan) {
    const rows = plan.querySelector("[data-activity-rows]");
    const total = plan.querySelector('[name="actividades-TOTAL_FORMS"]');
    const template = plan.querySelector("[data-empty-activity]");
    const firstNumber = Number(plan.dataset.nextNumber || 1);

    const visibleRows = () => [...rows.querySelectorAll("[data-activity-row]")].filter((row) => !row.hidden);
    const updateCodes = () => {
      visibleRows().forEach((row, index) => {
        row.querySelector(".activity-code").value = `${plan.dataset.codigo || ""}-A${String(firstNumber + index).padStart(2, "0")}`;
      });
    };

    const bindRemove = (row) => {
      row.querySelector("[data-remove-activity]").addEventListener("click", () => {
        if (visibleRows().length === 1) return;
        const deleteInput = row.querySelector('input[name$="-DELETE"]');
        if (deleteInput) deleteInput.checked = true;
        row.hidden = true;
        updateCodes();
      });
    };

    visibleRows().forEach(bindRemove);
    plan.querySelector("[data-add-activity]").addEventListener("click", () => {
      const index = Number(total.value);
      const fragment = template.content.cloneNode(true);
      const row = fragment.querySelector("[data-activity-row]");
      row.innerHTML = row.innerHTML.replaceAll("__prefix__", String(index));
      rows.appendChild(fragment);
      total.value = String(index + 1);
      bindRemove(rows.lastElementChild);
      updateCodes();
    });
    updateCodes();

    const confirmation = document.querySelector("[data-activity-confirm]");
    const confirmButton = confirmation?.querySelector("[data-confirm-activities]");
    const cancelButton = confirmation?.querySelector("[data-cancel-activities]");
    const saveButton = plan.querySelector("[data-save-activities]");
    let confirmed = false;

    const closeConfirmation = () => {
      confirmation.hidden = true;
      document.body.classList.remove("activity-modal-open");
      saveButton.focus();
    };

    plan.addEventListener("submit", (event) => {
      if (confirmed || !confirmation) {
        confirmed = false;
        return;
      }
      event.preventDefault();
      confirmation.hidden = false;
      document.body.classList.add("activity-modal-open");
      confirmButton.focus();
    });

    cancelButton?.addEventListener("click", closeConfirmation);
    confirmButton?.addEventListener("click", () => {
      confirmed = true;
      confirmation.hidden = true;
      document.body.classList.remove("activity-modal-open");
      plan.requestSubmit(saveButton);
    });
    confirmation?.addEventListener("click", (event) => {
      if (event.target === confirmation) closeConfirmation();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && confirmation && !confirmation.hidden) closeConfirmation();
    });
  }

  const scroller = document.querySelector("[data-activity-scroll]");
  const scrollbar = document.querySelector("[data-activity-scrollbar]");
  const track = document.querySelector("[data-activity-scrollbar-track]");
  const table = document.querySelector("[data-activity-table]");
  if (scroller && scrollbar && track && table) {
    let syncing = false;
    const updateTrack = () => {
      track.style.width = `${table.scrollWidth}px`;
      scrollbar.hidden = table.scrollWidth <= scroller.clientWidth;
    };
    const synchronize = (source, target) => {
      if (syncing) return;
      syncing = true;
      target.scrollLeft = source.scrollLeft;
      syncing = false;
    };
    scrollbar.addEventListener("scroll", () => synchronize(scrollbar, scroller));
    scroller.addEventListener("scroll", () => synchronize(scroller, scrollbar));
    window.addEventListener("resize", updateTrack);
    if (window.ResizeObserver) new ResizeObserver(updateTrack).observe(table);
    updateTrack();
  }
});
