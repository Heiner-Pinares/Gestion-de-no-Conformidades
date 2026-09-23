document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-cause-form]");
  if (!form) return;

  const accordions = [...form.querySelectorAll("details.cause-accordion")];
  accordions.forEach((accordion) => {
    accordion.addEventListener("toggle", () => {
      if (!accordion.open) return;
      accordions.forEach((other) => {
        if (other !== accordion) other.open = false;
      });
    });
  });

  const controlDetails = form.querySelector("[data-control-details]");
  const controlQuestion = [...form.querySelectorAll('input[name="r_4_1"]')];
  const syncControl = () => {
    if (!controlDetails) return;
    const enabled = controlQuestion.some((option) => option.checked && option.value === "SI");
    controlDetails.disabled = !enabled;
    controlDetails.classList.toggle("is-disabled", !enabled);
  };
  controlQuestion.forEach((option) => option.addEventListener("change", syncControl));
  syncControl();
});
