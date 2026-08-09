const $ = (selector) => document.querySelector(selector);

async function api(path, body) {
  const options = body === undefined ? { method: "GET" } : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const response = await fetch(path, options);
  const text = await response.text();
  try { return { ok: response.ok, data: JSON.parse(text) }; }
  catch { return { ok: false, data: { detail: text.slice(0, 200) } }; }
}

const themes = ["light", "dark"];
let theme = localStorage.getItem("theme");
if (!themes.includes(theme)) theme = "light";
function applyTheme() {
  document.documentElement.setAttribute("data-theme", theme);
  $("#theme-toggle").textContent = theme === "light" ? "Use dark mode" : "Use light mode";
  $("#theme-toggle").setAttribute("aria-pressed", String(theme === "dark"));
  localStorage.setItem("theme", theme);
}
$("#theme-toggle").addEventListener("click", () => {
  theme = themes[(themes.indexOf(theme) + 1) % themes.length];
  applyTheme();
});
applyTheme();

const stream = $("#stream");
let runId = null;
let currentCase = null;

function setProgress(stage, finished = false) {
  document.querySelectorAll("#workflow-progress li").forEach((item, index) => {
    const number = index + 1;
    item.classList.toggle("is-complete", number < stage || (finished && number <= stage));
    item.classList.toggle("is-active", number === stage && !finished);
    if (number === stage && !finished) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
}

function log(agent, message, why = "", tone = "") {
  const event = document.createElement("div");
  event.className = `event ${tone}`;
  const badge = document.createElement("span");
  badge.className = "agent";
  badge.textContent = agent;
  const content = document.createElement("div");
  content.textContent = message;
  if (why) {
    const detail = document.createElement("div");
    detail.className = "why";
    detail.textContent = why;
    content.append(detail);
  }
  event.append(badge, content);
  stream.prepend(event);
}

function addOptions(select, values) {
  select.replaceChildren();
  for (const value of values) {
    const option = document.createElement("option");
    option.value = typeof value === "string" ? value : value.key;
    option.textContent = typeof value === "string"
      ? value.replaceAll("_", " ")
      : `${value.title} — ${value.routed_to}`;
    select.append(option);
  }
}

async function refreshClock() {
  const { ok, data } = await api("/sim/state");
  $("#clock-now").textContent = ok
    ? new Date(data.simulated_now).toUTCString().replace(" GMT", "")
    : "unavailable";
}

async function boot() {
  const [letters, evidence] = await Promise.all([
    api("/sixty-days/fixtures"),
    api("/sixty-days/evidence/fixtures"),
  ]);
  if (!letters.ok || !evidence.ok) {
    $("#measurement").textContent = "Fixture catalogues unavailable.";
    return;
  }
  $("#measurement").textContent =
    `${letters.data.measured.recorded_calls} recorded letter calls: ` +
    `${letters.data.measured.correct}/${letters.data.measured.total} fields; ` +
    `${evidence.data.measured.recorded_calls} recorded photo calls: ` +
    `${evidence.data.measured.correct}/${evidence.data.measured.total} checks.`;
  addOptions($("#fixture"), letters.data.fixtures);
  addOptions($("#evidence-fixture"), evidence.data.fixtures);
  $("#fixture").value = "damage_and_insurance";
  $("#evidence-fixture").value = "damage_close_bad";
}

function renderPlan(data) {
  const target = $("#case-plan");
  target.replaceChildren();
  const deadline = document.createElement("p");
  deadline.textContent = `Deadline: ${data.deadline} (${data.days_in_window}-day window)`;
  target.append(deadline);
  if (data.deadline_conflict) {
    const conflict = document.createElement("p");
    conflict.className = "callout danger";
    conflict.textContent = data.deadline_conflict;
    target.append(conflict);
  }
  for (const deficiency of data.deficiencies) {
    const card = document.createElement("div");
    card.className = "card compact";
    const heading = document.createElement("h4");
    heading.textContent = deficiency.plain_language;
    const quote = document.createElement("p");
    quote.className = "quote";
    quote.textContent = `“${deficiency.quoted_text}”`;
    card.append(heading, quote);
    target.append(card);
  }
  const routeHeading = document.createElement("h4");
  routeHeading.textContent = "Evidence routes";
  target.append(routeHeading);
  const list = document.createElement("ul");
  for (const requirement of data.requirements) {
    const item = document.createElement("li");
    item.textContent = `${requirement.title} → ${requirement.routed_to}`;
    list.append(item);
  }
  target.append(list);
}

function resetDemoUi() {
  currentCase = null;
  runId = null;
  setProgress(1);
  stream.replaceChildren();
  log("demo preset", "Preparing a fresh synthetic case.",
      "No stored case or audit record is deleted.");
  $("#case-plan").replaceChildren();
  $("#letter-image").hidden = true;
  $("#evidence-image").hidden = true;
  $("#prepared-request").textContent = "";
  $("#packet-status").textContent = "No packet built.";
  $("#applicant-statement").value = "";
  $("#evidence-fixture").value = "damage_close_bad";
  $("#btn-screen").textContent = "Screen close photo (expected retake)";
  $("#request-requirement").replaceChildren();
  $("#request-requirement").disabled = true;
  for (const selector of [
    "#btn-screen", "#btn-prepare", "#btn-day3", "#btn-day52",
    "#btn-day58", "#btn-packet", "#btn-pdf",
  ]) {
    $(selector).disabled = true;
  }
}

$("#btn-open").addEventListener("click", async () => {
  const fixture = $("#fixture").value;
  const openButton = $("#btn-open");
  openButton.disabled = true;
  openButton.textContent = "Anchoring the demo clock...";
  resetDemoUi();
  const preset = await api("/sixty-days/demo/anchor", { fixture });
  if (!preset.ok) {
    log("demo preset", preset.data.detail || "Demo clock could not be anchored.", "", "reject");
    openButton.disabled = false;
    openButton.textContent = "Start guided demo with this letter";
    return;
  }
  await refreshClock();
  log("demo preset", "Clock anchored to the selected synthetic letter date.",
      "The same recorded fixture now behaves identically during every rehearsal.", "accept");
  const { ok, data } = await api("/sixty-days/cases", {
    fixture,
    applicant_ref: `DEMO-${fixture}`,
  });
  if (!ok) {
    log("letter reader", data.detail || "Case failed to open.", "", "reject");
    openButton.disabled = false;
    openButton.textContent = "Start guided demo with this letter";
    return;
  }
  currentCase = data;
  runId = data.run_id;
  $("#letter-image").src = `/sixty-days/fixtures/${fixture}/image`;
  $("#letter-image").hidden = false;
  const plannedSend = new Date(`${data.letter_date}T09:00:00Z`);
  plannedSend.setUTCDate(plannedSend.getUTCDate() + 5);
  $("#requested-on").value = plannedSend.toISOString().slice(0, 10);
  renderPlan(data);
  log("letter reader", `${data.deficiencies.length} quoted reason(s) survived verification.`,
      `${data.redacted} identifier(s) removed before downstream storage.`, "accept");
  log("evidence planner", `${data.requirements.length} concrete item(s) routed.`,
      data.requirements.map((item) => `${item.key} → ${item.routed_to}`).join("; "), "accept");
  log("deadline keeper", `${data.wakes.length} wakes registered through ${data.deadline}.`,
      "The agent is now asleep.", "accept");

  const requestable = data.requirements.filter(
    (item) => item.source === "third_party" || item.source === "public_record"
  );
  addOptions($("#request-requirement"), requestable);
  if (requestable.length) {
    const preferred = requestable.find((item) => item.key === "insurance_denial") || requestable[0];
    $("#request-requirement").value = preferred.key;
  }
  $("#request-requirement").disabled = requestable.length === 0;
  $("#btn-prepare").disabled = requestable.length === 0;
  $("#btn-screen").disabled = !data.requirements.some((item) => item.key === "photo_wide");
  for (const button of ["#btn-day3", "#btn-day52", "#btn-day58", "#btn-packet", "#btn-pdf"]) {
    $(button).disabled = false;
  }
  openButton.disabled = false;
  openButton.textContent = "Restart guided demo with this letter";
  setProgress(2);
});

$("#btn-screen").addEventListener("click", async () => {
  if (!currentCase) return;
  const fixture = $("#evidence-fixture").value;
  $("#evidence-image").src = `/sixty-days/evidence/fixtures/${fixture}/image`;
  $("#evidence-image").hidden = false;
  const { ok, data } = await api(
    `/sixty-days/cases/${currentCase.case_id}/evidence/check`,
    { fixture, requirement_key: "photo_wide" },
  );
  if (!ok) {
    log("evidence checker", data.detail || "Evidence check failed.", "", "reject");
    return;
  }
  const tone = data.decision === "ready_for_review" ? "accept" : "reject";
  log("evidence checker", data.decision.replaceAll("_", " "), data.guidance, tone);
  if (fixture === "damage_close_bad") {
    $("#evidence-fixture").value = "damage_wide_good";
    $("#btn-screen").textContent = "Screen wider comparison (expected review)";
    log("demo preset", "The wider comparison is selected for the next click.",
        "This makes the retake-to-review difference visible without hidden setup.");
  } else {
    $("#btn-screen").textContent = "Screen this photo again";
  }
  setProgress(3);
});

$("#btn-prepare").addEventListener("click", async () => {
  if (!currentCase) return;
  const { ok, data } = await api(
    `/sixty-days/cases/${currentCase.case_id}/requests/prepare`,
    {
      requirement_key: $("#request-requirement").value,
      requested_on: $("#requested-on").value,
    },
  );
  if (!ok) {
    log("request preparer", data.detail || "Request preparation failed.", "", "reject");
    return;
  }
  $("#prepared-request").textContent =
    `${data.subject}. Status: ${data.status}; delivery: ${data.delivery}. ` +
    `If there is no reply, the next check is ${data.tracking.due_at}.`;
  log("request preparer", "Draft prepared; nothing was sent.",
      `The applicant sends it. A no-reply check is registered for ${data.tracking.due_at}.`,
      "accept");
  setProgress(4);
});

async function packetBody() {
  return { applicant_statement: $("#applicant-statement").value };
}

$("#btn-packet").addEventListener("click", async () => {
  if (!currentCase) return;
  const { ok, data } = await api(
    `/sixty-days/cases/${currentCase.case_id}/packet`,
    await packetBody(),
  );
  if (!ok) {
    log("packet builder", data.detail || "Packet build failed.", "", "reject");
    return;
  }
  setProgress(4, true);
  $("#packet-status").textContent = data.missing.length
    ? `Partial draft: ${data.missing.length} item(s) still listed as missing.`
    : "Draft ready for the applicant’s page-by-page review.";
  log("packet verifier", `${data.verified_statements.length} letter statement(s) quote-grounded.`,
      `${data.missing.length} missing item(s) remain visible; the packet is not submitted.`,
      "accept");
});

$("#btn-pdf").addEventListener("click", async () => {
  if (!currentCase) return;
  const response = await fetch(
    `/sixty-days/cases/${currentCase.case_id}/packet.pdf`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await packetBody()),
    },
  );
  if (!response.ok) {
    log("packet renderer", "Draft PDF failed to render.", "", "reject");
    return;
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `draft-appeal-${currentCase.case_id}.pdf`;
  link.click();
  URL.revokeObjectURL(url);
  log("packet renderer", "Draft PDF downloaded for applicant review.",
      "No send or submission action occurred.", "accept");
});

async function advance(days, label) {
  const { ok, data } = await api("/sim/advance", { days });
  if (!ok) {
    log("clock", data.detail || "Advance failed.", "", "reject");
    return;
  }
  await refreshClock();
  const wakes = (data.woke || []).filter((wake) => wake.run_id === runId);
  if (!wakes.length) log("clock", `${label}: nothing due.`, "Silence is the expected state.");
  for (const wake of wakes) {
    log("deadline keeper", `Woke itself: ${wake.kind}.`,
        "The scheduler found this event due; nobody clicked an agent action.", "accept");
  }
}
$("#btn-day3").addEventListener("click", () => advance(3, "Advanced 3 days"));
$("#btn-day52").addEventListener("click", () => advance(49, "Advanced 49 more days"));
$("#btn-day58").addEventListener("click", () => advance(6, "Advanced 6 more days"));

boot();
refreshClock();
setInterval(refreshClock, 15000);
