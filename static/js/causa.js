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

  form.querySelectorAll("details.cause-accordion").forEach((accordion) => {
    const row = accordion.querySelector("[data-other-row]");
    const add = accordion.querySelector("[data-add-other]");
    const undo = accordion.querySelector("[data-undo-other]");
    if (!row || !add || !undo) return;
    const active = row.querySelector('input[type="hidden"][name^="a_"]');
    const question = row.querySelector('input[name^="t_"]');
    const comment = row.querySelector('input[name^="c_"]');
    const answers = [...row.querySelectorAll('input[type="radio"]')];

    add.addEventListener("click", () => {
      active.value = "1";
      row.hidden = false;
      add.hidden = true;
      question.focus();
    });
    undo.addEventListener("click", () => {
      active.value = "0";
      question.value = "";
      comment.value = "";
      answers.forEach((answer) => { answer.checked = false; });
      row.hidden = true;
      add.hidden = false;
      add.focus();
    });
  });
});
