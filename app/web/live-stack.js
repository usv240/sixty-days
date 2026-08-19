(() => {
  const header = document.querySelector("header.site .bar");
  if (!header || header.querySelector("[data-live-stack]")) return;

  const groups = [
    ["Live request path", ["Gemini 3.5 Flash on Vertex AI", "Cloud Run", "Firestore", "Cloud Scheduler", "Cloud Trace and Logging", "Secret Manager"]],
    ["Additional Google AI", ["Gemma 4 MaaS privacy review", "Gemini 3.1 Flash Image and Veo 3.1 Fast recorded media"]],
  ];

  const widget = document.createElement("div");
  widget.className = "live-stack";
  widget.dataset.liveStack = "";
  widget.innerHTML = `
    <button class="live-stack-trigger" type="button" aria-expanded="false" aria-controls="live-stack-panel">
      <span class="live-stack-dot" aria-hidden="true"></span><span>Live stack</span>
    </button>
    <section class="live-stack-panel" id="live-stack-panel" aria-label="Technology used by Sixty Days">
      <div class="live-stack-heading"><span class="live-stack-dot" aria-hidden="true"></span><div><strong>Running on Google Cloud</strong><small>Verified services in this build</small></div></div>
      ${groups.map(([title, items]) => `<div class="live-stack-group"><b>${title}</b><ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul></div>`).join("")}
      <p class="live-stack-note">Technology used; no endorsement implied.</p>
    </section>`;

  const theme = header.querySelector(".theme-toggle");
  const actions = document.createElement("div");
  actions.className = "header-actions";
  header.append(actions);
  actions.append(widget);
  if (theme) actions.append(theme);

  const trigger = widget.querySelector(".live-stack-trigger");
  const close = () => { widget.classList.remove("is-open"); trigger.setAttribute("aria-expanded", "false"); };
  trigger.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = !widget.classList.contains("is-open");
    close();
    if (open) { widget.classList.add("is-open"); trigger.setAttribute("aria-expanded", "true"); }
  });
  widget.addEventListener("click", (event) => event.stopPropagation());
  document.addEventListener("click", close);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") { close(); trigger.focus(); } });
})();
