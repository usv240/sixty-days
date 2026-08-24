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

/* --- Plain-language popovers -------------------------------------------- */

// Some words on this page cannot be avoided: appeal, decision letter, reminder, draft packet.
// Rather than assume them or bury a glossary in a footer, each is explained where it is met.
let glossary = {};
const popover = $("#popover");
let openTrigger = null;

fetch("/static/glossary.json").then((r) => r.json()).then((g) => { glossary = g; }).catch(() => {});

function closePopover() {
  popover.hidden = true;
  if (openTrigger) { openTrigger.setAttribute("aria-expanded", "false"); openTrigger = null; }
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest(".info");
  if (!trigger) { if (!event.target.closest("#popover")) closePopover(); return; }
  event.preventDefault();
  const entry = glossary[trigger.dataset.info];
  if (!entry) return;
  if (openTrigger === trigger) { closePopover(); return; }

  popover.replaceChildren();
  const title = document.createElement("h4");
  title.textContent = entry.title;
  const plain = document.createElement("p");
  plain.textContent = entry.plain;
  const why = document.createElement("p");
  why.className = "why";
  const whyLabel = document.createElement("b");
  whyLabel.textContent = "Why it matters here: ";
  why.append(whyLabel, document.createTextNode(entry.why));
  const link = document.createElement("a");
  link.href = entry.url;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = `Source: ${entry.source}`;
  popover.append(title, plain, why, link);
  popover.hidden = false;

  const rect = trigger.getBoundingClientRect();
  const width = Math.min(340, window.innerWidth - 32);
  popover.style.width = `${width}px`;
  let left = rect.left + window.scrollX;
  left = Math.max(16, Math.min(left, window.innerWidth - width - 16));
  popover.style.left = `${left}px`;
  popover.style.top = `${rect.bottom + window.scrollY + 8}px`;

  trigger.setAttribute("aria-expanded", "true");
  openTrigger = trigger;
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !popover.hidden) {
    const trigger = openTrigger;
    closePopover();
    if (trigger) trigger.focus();
  }
});

const stream = $("#stream");
let runId = null;
let currentCase = null;

const STEP_STATE_LABEL = { complete: "Done", current: "Current", upcoming: "Upcoming" };

function setProgress(stage, finished = false) {
  document.querySelectorAll("#workflow-progress li").forEach((item, index) => {
    const number = index + 1;
    item.classList.toggle("is-complete", number < stage || (finished && number <= stage));
    item.classList.toggle("is-active", number === stage && !finished);
    if (number === stage && !finished) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  });
  // The stage cards collapse everything except the current step, so the rail and the console
  // can never disagree about what the applicant is supposed to do next.
  document.querySelectorAll(".control-group[data-workflow-step]").forEach((group) => {
    const number = Number(group.dataset.workflowStep);
    const state = number < stage || (finished && number <= stage)
      ? "complete"
      : number === stage ? "current" : "upcoming";
    group.dataset.state = state;
    // A completed run would otherwise collapse every stage and leave nothing to act on, so the
    // last stage stays open with its controls available for a second look.
    group.classList.toggle("is-open", finished && number === stage);
    const badge = group.querySelector(".step-state");
    if (badge) badge.textContent = STEP_STATE_LABEL[state];
  });
}

// --- The case timeline ---------------------------------------------------
// A log answers "what happened, in order", which grows without bound, so any box holding one is
// eventually cramped or scrolling. A judge is asking two fixed-size questions instead: where is
// this case inside its sixty days, and what did the agent just do. So the reminders become marks
// on the window they live on, the clock walks across it, and marks fill as they fire. The height
// never changes, however long the case runs.

let timelineWindow = null;

// The reminders that end the case read differently from the ones that continue it.
const TERMINAL_KINDS = new Set(["build_partial", "final_alert"]);

function renderTimeline(data) {
  const track = $("#timeline-markers");
  const start = Date.parse(`${data.letter_date}T00:00:00Z`);
  const end = Date.parse(`${data.deadline}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return;
  timelineWindow = { start, end };

  track.replaceChildren();
  for (const wake of data.wakes || []) {
    const due = Date.parse(wake.due_at);
    if (!Number.isFinite(due)) continue;
    const marker = document.createElement("span");
    marker.className = `timeline-marker${TERMINAL_KINDS.has(wake.kind) ? " is-terminal" : ""}`;
    marker.style.left = `${((due - start) / (end - start)) * 100}%`;
    marker.dataset.due = String(due);
    marker.title = `${plainWake(wake.kind)} — due ${String(wake.due_at).slice(0, 10)}`;
    track.append(marker);
  }

  $("#timeline-start").textContent = data.letter_date;
  $("#timeline-end").textContent = `${data.deadline} · deadline`;
  $("#case-timeline").hidden = false;
  updateTimeline();
}

// Recomputed from the clock rather than tracked per event: a mark is filled when its date has
// passed. Self-correcting, and it needs no bookkeeping to match fired wakes back to marks.
function updateTimeline(nowIso) {
  if (!timelineWindow) return;
  const now = Date.parse(nowIso || $("#clock-now").dataset.iso || "");
  if (!Number.isFinite(now)) return;

  const { start, end } = timelineWindow;
  const progress = Math.max(0, Math.min(1, (now - start) / (end - start)));
  $("#timeline-fill").style.width = `${progress * 100}%`;
  const cursor = $("#timeline-now");
  cursor.style.left = `${progress * 100}%`;
  cursor.hidden = false;

  for (const dot of document.querySelectorAll(".timeline-marker")) {
    dot.classList.toggle("is-fired", Number(dot.dataset.due) <= now);
  }
}

function resetTimeline() {
  timelineWindow = null;
  $("#case-timeline").hidden = true;
  $("#timeline-markers").replaceChildren();
  $("#timeline-now").hidden = true;
  $("#timeline-fill").style.width = "0";
}

// One thing happened most recently, and it is the thing worth reading at full size.
function setLatest(agent, message, why, tone) {
  const latest = $("#latest-event");
  latest.className = `latest ${tone || ""}`.trim();
  latest.replaceChildren();
  const role = document.createElement("span");
  role.className = "latest-role";
  role.textContent = agent;
  const what = document.createElement("b");
  what.className = "latest-what";
  what.textContent = message;
  latest.append(role, what);
  if (why) {
    const reason = document.createElement("span");
    reason.className = "latest-why";
    reason.textContent = why;
    latest.append(reason);
  }
}

function refreshStepCount() {
  const count = stream.querySelectorAll(".event").length;
  $("#all-steps-count").textContent = count
    ? `Show all ${count} step${count === 1 ? "" : "s"}`
    : "No earlier steps yet";
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
  setLatest(agent, message, why, tone);
  refreshStepCount();
}

// The judge should be able to see exactly what the agent was handed, before it is handed over.
// Previewing on selection rather than on submit is what makes the input auditable rather than
// implied: the picture on screen is the same bytes the model reads.
function previewSource(kind, fixture) {
  const image = $(`#${kind}-image`);
  const frame = image.closest(".source-frame");
  const state = $(`#${kind}-state`);
  const caption = $(`#${kind}-caption`);
  const label = String(fixture || "").replaceAll("_", " ");

  const zoom = $(`#${kind}-zoom`);

  if (!fixture) {
    image.hidden = true;
    image.removeAttribute("src");
    zoom.hidden = true;
    frame.classList.remove("is-loading");
    state.textContent = kind === "letter"
      ? "Select a letter to preview it."
      : "Select a photo to preview it.";
    return;
  }

  const source = kind === "letter"
    ? `/sixty-days/fixtures/${fixture}/image`
    : `/sixty-days/evidence/fixtures/${fixture}/image`;

  caption.textContent = kind === "letter" ? `Decision letter: ${label}` : `Evidence photo: ${label}`;
  state.textContent = "Loading the synthetic fixture…";
  frame.classList.add("is-loading");
  image.hidden = true;

  image.onload = () => {
    frame.classList.remove("is-loading");
    image.hidden = false;
    zoom.href = source;
    zoom.hidden = false;
    state.textContent = kind === "letter"
      ? "The exact page Gemini 3.5 Flash transcribes."
      : "The exact photograph the framing check screens.";
  };
  image.onerror = () => {
    frame.classList.remove("is-loading");
    image.hidden = true;
    zoom.hidden = true;
    state.textContent = "This fixture preview could not be loaded.";
  };
  image.src = source;
}

function showEvidenceVerdict(text, tone) {
  const verdict = $("#evidence-verdict");
  if (!text) {
    verdict.hidden = true;
    verdict.textContent = "";
    verdict.className = "source-verdict";
    return;
  }
  verdict.className = `source-verdict ${tone}`;
  verdict.textContent = text;
  verdict.hidden = false;
}

function addOptions(select, values) {
  select.replaceChildren();
  for (const value of values) {
    const option = document.createElement("option");
    option.value = typeof value === "string" ? value : value.key;
    option.textContent = typeof value === "string"
      ? value.replaceAll("_", " ")
      : `${value.title} - ${value.routed_to}`;
    select.append(option);
  }
}

// Wall-clock proof, kept separate from the simulated demo clock on purpose: conflating the two
// is exactly the overstatement this project refuses to make elsewhere.
// Internal names are for the code. People get sentences.
const WAKE_IN_PLAIN = {
  understood_check: "checked whether the summary actually made sense",
  nudge: "listed what is still missing",
  replan: "changed the approach, because the same request had failed repeatedly",
  escalate: "surfaced the free legal-aid option, leaving the choice with the applicant",
  build_partial: "assembled a draft from whatever has been gathered so far",
  final_alert: "gave the final warning, two days before the deadline",
  packet_safeguard: "assembled a draft from whatever has been gathered so far",
};

function plainWake(kind) {
  const key = String(kind || "");
  if (WAKE_IN_PLAIN[key]) return WAKE_IN_PLAIN[key];
  if (key.startsWith("chase:")) {
    const what = key.slice("chase:".length).replaceAll("_", " ");
    return `followed up, because there was still no reply about the ${what}`;
  }
  return key.replaceAll("_", " ").replaceAll(":", ": ");
}

// The honest objection to the whole demo is that a person pressed a button. This answers it
// without a simulated clock: a reminder registered on the wall clock, executed by the scheduled
// worker, while this page does nothing but ask whether it has happened yet.
let liveProofTimer = null;

async function pollLiveProof(wakeId, dueAt) {
  const status = $("#live-proof-status");
  const { ok, data } = await api(`/sixty-days/live-proof/${wakeId}`);
  if (!ok) return;

  if (data.fired) {
    window.clearInterval(liveProofTimer);
    liveProofTimer = null;
    status.className = "small fired";
    status.textContent =
      `Cloud Scheduler fired it at ${new Date(data.fired_at).toLocaleTimeString()}. Nobody pressed anything.`;
    // The rail column is too narrow for the worker id, but it is the part that makes this checkable,
    // so it goes where there is room to read it: on hover, and in the activity trail.
    status.title = data.worker ? `Executed by ${data.worker}` : "";
    log("deadline keeper", "A reminder fired on the real clock.",
        data.revision
          ? `Registered earlier on the real clock and executed by Cloud Run revision ${data.revision}, not by this page.`
          : "Registered earlier on the real clock and executed by the scheduled worker, not by this page.",
        "accept");
    $("#btn-live-proof").disabled = false;
    $("#btn-live-proof").textContent = "Set another one";
    return;
  }

  const left = data.seconds_until_due ?? Math.max(0, Math.round((dueAt - Date.now()) / 1000));
  status.className = "small waiting";
  status.textContent = left > 0
    ? `Waiting. Due in ${left}s, then the next scheduler pass picks it up.`
    : "Due now. Waiting for the next scheduler pass.";
}

$("#btn-live-proof").addEventListener("click", async () => {
  const button = $("#btn-live-proof");
  const status = $("#live-proof-status");
  button.disabled = true;
  button.textContent = "Registering…";
  const { ok, data } = await api("/sixty-days/live-proof", {});
  if (!ok) {
    status.className = "small muted";
    status.textContent = data.detail || "The reminder could not be registered.";
    button.disabled = false;
    button.textContent = "Set a reminder on the real clock";
    return;
  }
  button.textContent = "Armed — leave it alone";
  log("deadline keeper", "Set a reminder a short way out on the real calendar.",
      "Nothing on this page will run it. The scheduled worker will.", "accept");

  const dueAt = new Date(data.due_at).getTime();
  status.className = "small waiting";
  status.textContent = `Waiting. Due in ${data.seconds_until_due}s.`;
  if (liveProofTimer) window.clearInterval(liveProofTimer);
  liveProofTimer = window.setInterval(() => pollLiveProof(data.wake_id, dueAt), 5000);
  pollLiveProof(data.wake_id, dueAt);
});

async function refreshLiveBudget() {
  const { ok, data } = await api("/sixty-days/live-check/budget");
  const label = $("#live-check-budget");
  const button = $("#btn-live-check");
  if (!ok) { label.textContent = "Live-call allowance unavailable."; return; }
  const left = data.your_calls_left ?? 0;
  button.disabled = !data.allowed;
  // One line. The old wording wrapped to two in the rail's column, and the second line only
  // repeated what the button already says once you press it.
  label.textContent = data.allowed
    ? `${left} of ${data.your_calls_allowed_today} live calls left today · takes 10-30s`
    : data.reason;
}

$("#btn-live-check").addEventListener("click", async () => {
  const button = $("#btn-live-check");
  const result = $("#live-check-result");
  button.disabled = true;
  button.textContent = "Calling Gemini 3.5 Flash…";
  result.hidden = true;
  const { ok, data } = await api("/sixty-days/live-check", {});
  button.textContent = "Read the letter live";
  if (!ok) {
    result.className = "live-result fail";
    result.textContent = data.detail || "The live call did not complete.";
    result.hidden = false;
    await refreshLiveBudget();
    return;
  }
  const perfect = data.correct === data.total;
  result.className = `live-result ${perfect ? "pass" : "fail"}`;
  result.replaceChildren();
  const headline = document.createElement("b");
  headline.textContent = `${data.correct} of ${data.total} fields correct, live`;
  result.append(headline);

  // "5 of 5" on its own is a number a judge has to take on trust: it names neither what was checked
  // nor what came back. Both are in the response and were being discarded. The five checks are
  // therefore listed by name, and the three the model answers in words show its answer beside the
  // truth it was graded against -- so the score can be re-derived by reading, not believed.
  // Short enough that five of them fit a narrow column as wrapped chips rather than five wrapped
  // list rows. The long form cost 130px in a box that already pushes the panes down.
  const LABEL = {
    letter_date: "letter date",
    determination: "decision",
    stated_deadline: "stated deadline",
    deficiency_kinds: "reasons",
    all_quotes_grounded: "quotes grounded",
  };
  const checks = document.createElement("ul");
  checks.className = "live-checks";
  for (const [key, passed] of Object.entries(data.fields || {})) {
    const item = document.createElement("li");
    item.className = passed ? "is-pass" : "is-fail";
    item.textContent = LABEL[key] || key.replaceAll("_", " ");
    checks.append(item);
  }
  result.append(checks);

  // What the model actually answered goes to the activity pane, not here. This card is one column
  // of a four-column rail, about 240px wide, and a date-value list in it wrapped, clipped mid-word,
  // and pushed the three panes below off a 900px screen. The pane beside it is twice as wide and is
  // already where "what just happened" is read.
  const answered = data.answered || {};
  const expected = data.expected || {};
  const parts = [];
  for (const [key, value] of Object.entries(answered)) {
    const label = LABEL[key] || key.replaceAll("_", " ");
    parts.push(value === expected[key]
      ? `${label} ${value}`
      : `${label} ${value} (truth: ${expected[key]})`);
  }
  if ((data.extracted_kinds || []).length) {
    parts.push(`reasons ${data.extracted_kinds.map((k) => k.replaceAll("_", " ")).join(" + ")}`);
  }
  const redacted = data.redacted_identifiers;
  const provenance =
    `It answered: ${parts.join(" · ")}. Read from the letter image on the left, no ` +
    `transcript supplied — ${data.model} on Vertex AI, ${data.elapsed_ms} ms, ` +
    `${redacted} identifier${redacted === 1 ? "" : "s"} removed before the model saw the text. ` +
    "No case was created and nothing was stored.";
  result.hidden = false;
  log("live model call",
      `${data.correct} of ${data.total} fields correct on a live Vertex AI call.`,
      provenance, perfect ? "accept" : "reject");
  await refreshLiveBudget();
});

async function refreshScheduler() {
  const pill = $("#scheduler-pill");
  const text = $("#scheduler-text");
  const { ok, data } = await api("/sixty-days/scheduler");
  pill.classList.remove("is-running", "is-stale");
  if (!ok || !data.status) {
    text.textContent = "Scheduler status unavailable";
    return;
  }
  if (data.status === "running") {
    pill.classList.add("is-running");
    const seconds = data.seconds_since_last_scan ?? 0;
    const ago = seconds < 90 ? `${seconds}s ago` : `${Math.round(seconds / 60)} min ago`;
    text.textContent = `Real scheduler woke this service ${ago}`;
  } else if (data.status === "stale") {
    pill.classList.add("is-stale");
    text.textContent = "Real scheduler has not reported recently";
  } else {
    text.textContent = "Real scheduler registered, no scan recorded yet";
  }
}

async function refreshClock() {
  const { ok, data } = await api("/sim/state");
  $("#clock-now").textContent = ok
    ? new Date(data.simulated_now).toUTCString().replace(" GMT", "")
    : "unavailable";
  if (ok) {
    $("#clock-now").dataset.iso = data.simulated_now;
    updateTimeline(data.simulated_now);
  }
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
  previewSource("letter", $("#fixture").value);
  previewSource("evidence", $("#evidence-fixture").value);
}

$("#fixture").addEventListener("change", (event) => {
  previewSource("letter", event.target.value);
});
$("#evidence-fixture").addEventListener("change", (event) => {
  previewSource("evidence", event.target.value);
  showEvidenceVerdict("", "");
});

function renderPlan(data) {
  // Same principle as the timeline: show the shape of the case, keep the evidence one click away.
  // The letter's exact wording is the safety-critical part and the longest text on the page, so it
  // is what gets folded rather than what gets dropped.
  // The deadline is not repeated here: the timeline in the pane beside this one already
  // shows it, marked at the end of the window it closes.
  const target = $("#case-plan");
  target.replaceChildren();

  if (data.deadline_conflict) {
    const conflict = document.createElement("p");
    conflict.className = "callout danger";
    conflict.textContent = data.deadline_conflict;
    target.append(conflict);
  }

  const reasons = document.createElement("ul");
  reasons.className = "plan-reasons";
  for (const deficiency of data.deficiencies) {
    const item = document.createElement("li");
    item.textContent = deficiency.plain_language;
    item.title = deficiency.plain_language;
    reasons.append(item);
  }
  target.append(reasons);

  // The claim is that every reason is copied from the letter. That has to remain checkable, so the
  // quotes stay in the page in full rather than being summarised away.
  if (data.deficiencies.length) {
    const quotes = document.createElement("details");
    quotes.className = "plan-quotes";
    const summary = document.createElement("summary");
    summary.textContent = `Show the letter's exact words (${data.deficiencies.length})`;
    quotes.append(summary);
    for (const deficiency of data.deficiencies) {
      const quote = document.createElement("blockquote");
      quote.className = "quote";
      quote.textContent = `\u201c${deficiency.quoted_text}\u201d`;
      quotes.append(quote);
    }
    target.append(quotes);
  }

  const routeHeading = document.createElement("p");
  routeHeading.className = "plan-subhead";
  routeHeading.textContent = "Who holds what";
  target.append(routeHeading);

  const routes = document.createElement("ul");
  routes.className = "plan-routes";
  for (const requirement of data.requirements) {
    const item = document.createElement("li");
    const what = document.createElement("b");
    what.textContent = requirement.title;
    const who = document.createElement("span");
    who.className = "route-holder";
    // The arrow lives here rather than in a ::before rule: one string, one place it can go wrong.
    who.textContent = `\u2192 ${requirement.routed_to}`;
    item.append(what, who);
    routes.append(item);
  }
  target.append(routes);
}

function resetDemoUi() {
  currentCase = null;
  runId = null;
  setProgress(1);
  stream.replaceChildren();
  refreshStepCount();
  log("demo preset", "Preparing a fresh synthetic case.",
      "No stored case or audit record is deleted.");
  $("#case-plan").replaceChildren();
  resetTimeline();
  showEvidenceVerdict("", "");
  $("#prepared-request").textContent = "";
  $("#packet-status").textContent = "No packet built.";
  lastLifecycleState = "";
  $("#applicant-statement").value = "";
  $("#evidence-fixture").value = "damage_close_bad";
  previewSource("evidence", "damage_close_bad");
  $("#btn-screen").textContent = "Screen close photo (expected retake)";
  $("#request-requirement").replaceChildren();
  $("#request-requirement").disabled = true;
  for (const selector of [
    "#btn-screen", "#btn-prepare", "#btn-day3", "#btn-day52",
    "#btn-day58", "#btn-day61", "#btn-packet", "#btn-pdf",
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
  previewSource("letter", fixture);
  const plannedSend = new Date(`${data.letter_date}T09:00:00Z`);
  plannedSend.setUTCDate(plannedSend.getUTCDate() + 5);
  $("#requested-on").value = plannedSend.toISOString().slice(0, 10);
  renderPlan(data);
  renderTimeline(data);
  log("letter reader", `Found ${data.deficiencies.length} reason(s) the letter actually gives.`,
      `Each one is copied word for word from the letter. ${data.redacted} personal detail(s) were removed first.`,
      "accept");
  log("evidence planner", `Worked out ${data.requirements.length} document(s) to gather, and who has each one.`,
      data.requirements.map((item) => `${item.title} - ask ${item.routed_to}`).join("; "), "accept");
  log("deadline keeper", `Set ${data.wakes.length} reminders for itself, up to the ${data.deadline} deadline.`,
      "It now waits. It will wake itself up on each of those dates without being asked.", "accept");

  const requestable = data.requirements.filter(
    (item) => item.source === "third_party" || item.source === "public_record"
  );
  addOptions($("#request-requirement"), requestable);
  if (requestable.length) {
    // The contractor record is the guided default because it is the one requirement with a
    // second route, so a judge gets to watch the agent change its own plan when no reply
    // comes back. The insurer record stays selectable and demonstrates the opposite case:
    // no alternative exists, so the agent refuses to guess and hands over to legal aid.
    const preferred = requestable.find((item) => item.key === "repair_record")
      || requestable.find((item) => item.key === "insurance_denial")
      || requestable[0];
    $("#request-requirement").value = preferred.key;
  }
  $("#request-requirement").disabled = requestable.length === 0;
  $("#btn-prepare").disabled = requestable.length === 0;
  $("#btn-screen").disabled = !data.requirements.some((item) => item.key === "photo_wide");
  for (const button of ["#btn-day3", "#btn-day52", "#btn-day58", "#btn-day61", "#btn-packet", "#btn-pdf"]) {
    $(button).disabled = false;
  }
  openButton.disabled = false;
  openButton.textContent = "Restart guided demo with this letter";
  setProgress(2);
});

$("#btn-screen").addEventListener("click", async () => {
  if (!currentCase) return;
  const fixture = $("#evidence-fixture").value;
  previewSource("evidence", fixture);
  const { ok, data } = await api(
    `/sixty-days/cases/${currentCase.case_id}/evidence/check`,
    { fixture, requirement_key: "photo_wide" },
  );
  if (!ok) {
    log("evidence checker", data.detail || "Evidence check failed.", "", "reject");
    return;
  }
  const tone = data.decision === "ready_for_review" ? "accept" : "reject";
  // The verdict has to name the photo it judged. Screening the close one immediately swaps the
  // preview to the wider one, ready for the next click, which left a "retake" message sitting
  // under a photo it was not about -- reading exactly as though the wider photo had been refused.
  const SCREENED = { damage_close_bad: "Close photo", damage_wide_good: "Wider photo" };
  const subject = SCREENED[fixture] || fixture.replaceAll("_", " ");
  log("evidence checker", `${subject}: ${data.decision.replaceAll("_", " ")}`, data.guidance, tone);
  showEvidenceVerdict(`${subject}: ${data.decision.replaceAll("_", " ")}. ${data.guidance}`, tone);
  if (fixture === "damage_close_bad") {
    $("#evidence-fixture").value = "damage_wide_good";
    previewSource("evidence", "damage_wide_good");
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
  log("request preparer", "Wrote the request. It was not sent.",
      `You send it yourself. If there is no reply by ${data.tracking.due_at}, it will check back.`,
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
  // "item(s)" is a shortcut taken for the writer's benefit, not the reader's, and these two lines
  // are read by someone deciding whether a half-finished appeal packet is honest about being
  // half-finished. Worth the ternary.
  const missing = data.missing.length;
  const items = (n) => `${n} item${n === 1 ? "" : "s"}`;
  const checked = data.verified_statements.length;
  $("#packet-status").textContent = missing
    ? `Partial draft: ${items(missing)} still listed as missing.`
    : "Draft ready for the applicant’s page-by-page review.";
  log("packet verifier",
      `Checked ${checked} statement${checked === 1 ? "" : "s"} against the letter's own words.`,
      `${items(missing)} still missing, and the draft says so. Nothing was submitted.`,
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

// Asked after every advance, because a case can finish quietly: everything gathered, or the window
// closing after the last reminder. Waiting for a wake to announce it would mean it never gets said.
let lastLifecycleState = "";
async function reportLifecycle() {
  if (!currentCase) return;
  const { ok, data } = await api(`/sixty-days/cases/${currentCase.case_id}/status`);
  if (!ok || !data.terminal || data.state === lastLifecycleState) return;
  lastLifecycleState = data.state;
  const headline = {
    resolved: "Case complete. It stopped scheduling reminders by itself.",
    exhausted: "Nothing left it can usefully chase. It stopped its own reminders.",
    deadline_passed: "The 60-day window has passed. It stopped its own reminders.",
  }[data.state] || "It closed the case by itself.";
  log("deadline keeper", headline, data.reason, data.state === "resolved" ? "accept" : "");
}

async function advance(days, label) {
  const { ok, data } = await api("/sim/advance", { days });
  if (!ok) {
    log("clock", data.detail || "Advance failed.", "", "reject");
    return;
  }
  await refreshClock();
  const wakes = (data.woke || []).filter((wake) => wake.run_id === runId);
  if (!wakes.length) log("clock", `${label}: nothing was due yet.`,
    "Most days there is nothing to do. Staying quiet is the normal state.");
  for (const wake of wakes) {
    const domain = wake.domain || {};
    log("deadline keeper", `It woke up on its own and ${plainWake(wake.kind)}.`,
        domain.detail || "The clock reached this date. Nobody pressed anything.",
        "accept");
    // Rerouting is the moment the agent stops reminding and starts deciding, so it gets its own
    // line rather than being buried in the generic wake detail.
    if (domain.action === "evidence_route_changed" && domain.replan) {
      const plan = domain.replan;
      log("evidence planner",
          `Changed its own plan: now getting "${plan.alternative_title}" from ${plan.alternative_routed_to}.`,
          `${plan.reason}${domain.drafted_request ? " The replacement request has been drafted for you to read." : ""}`,
          "accept");
    }
    if (domain.action === "third_party_reply_check_due" && domain.replan
        && domain.replan.alternative_key && !domain.replan.changed
        && domain.replan.handoff !== "legal_aid") {
      log("evidence planner", "Checked the route and left it alone.",
          domain.replan.reason, "accept");
    }
    if (domain.action === "third_party_reply_check_due" && domain.replan
        && domain.replan.handoff === "legal_aid") {
      log("evidence planner", "No other route exists for this record.",
          `${domain.replan.reason} Free legal aid is surfaced instead of guessing an alternative.`,
          "reject");
    }
    // Stopping is a decision too, and the applicant should see it happen rather than just notice
    // the reminders went quiet.
    const life = domain.lifecycle;
    if (life && life.terminal) {
      const headline = {
        resolved: "Case complete. It stopped scheduling reminders by itself.",
        exhausted: "Nothing left it can usefully chase. It stopped by itself.",
        deadline_passed: "The 60-day window has passed. It stopped its own reminders.",
      }[life.state] || "It closed the case by itself.";
      const cancelled = life.cancelled_reminders
        ? ` ${life.cancelled_reminders} remaining reminder(s) were cancelled.`
        : "";
      log("deadline keeper", headline, life.reason + cancelled,
          life.state === "resolved" ? "accept" : "");
    }
    if (domain.action === "partial_packet_built") {
      $("#packet-status").textContent = `${domain.packet_status}: ${(domain.missing || []).join(" | ")}`;
      log("packet builder", "Built a draft appeal packet by itself.",
          "It still shows everything that is missing, and nothing was sent to anyone.", "accept");
    }
  }
  await reportLifecycle();
}
$("#btn-day3").addEventListener("click", () => advance(3, "Advanced 3 days"));
$("#btn-day52").addEventListener("click", () => advance(49, "Advanced 49 more days"));
$("#btn-day58").addEventListener("click", () => advance(6, "Advanced 6 more days"));
// Past the deadline on purpose: the last thing a judge should see is the agent deciding it
// is finished and switching itself off, rather than the reminders merely going quiet.
$("#btn-day61").addEventListener("click", () => advance(3, "Advanced 3 more days"));

$("#letter-image").closest(".source-frame").classList.add("is-letter");
refreshStepCount();


// Starting over is the one control a judge needs at every point, including after the run ends.
$("#btn-restart").addEventListener("click", () => {
  $("#btn-open").click();
});

boot();
refreshClock();
refreshScheduler();
refreshLiveBudget();
setInterval(refreshClock, 15000);
setInterval(refreshScheduler, 20000);
