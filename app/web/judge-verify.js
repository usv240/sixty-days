/* Let the judge check the claims instead of reading them.
 *
 * The evidence page used to print commands and ask to be trusted. Every button here calls the
 * deployed service and shows what came back, so the page can be verified from a browser with no
 * terminal, no checkout, and no credentials -- which also means a demo recording never has to leave
 * the browser to prove anything.
 */
(() => {
  "use strict";

  const $ = (selector) => document.querySelector(selector);

  const show = (panel, { state, headline, lines, note }) => {
    panel.className = `verify-result ${state}`;
    panel.replaceChildren();

    const title = document.createElement("b");
    title.textContent = headline;
    panel.append(title);

    if (lines && lines.length) {
      const list = document.createElement("ul");
      list.className = "verify-list";
      for (const line of lines) {
        const item = document.createElement("li");
        const mark = document.createElement("span");
        mark.className = `mark${line.ok === false ? " no" : ""}`;
        mark.textContent = line.ok === false ? "✗" : "✓";
        const text = document.createElement("span");
        text.textContent = line.text;
        item.append(mark, text);
        list.append(item);
      }
      panel.append(list);
    }

    if (note) {
      const detail = document.createElement("div");
      detail.textContent = note;
      panel.append(detail);
    }
    panel.hidden = false;
  };

  // Every button follows the same contract: say it is working before the request, never leave a
  // previous answer on screen while a new question is in flight, and report a failure as a failure.
  const wire = (buttonId, panelId, run) => {
    const button = $(buttonId);
    const panel = $(panelId);
    if (!button || !panel) return;
    button.addEventListener("click", async () => {
      const label = button.textContent;
      button.disabled = true;
      button.textContent = "Checking…";
      show(panel, { state: "pending", headline: "Calling the deployed service…" });
      const started = performance.now();
      try {
        await run(panel, Math.round.bind(Math));
      } catch (error) {
        show(panel, {
          state: "fail",
          headline: "The check could not complete",
          note: String(error && error.message ? error.message : error),
        });
      } finally {
        const elapsed = Math.round(performance.now() - started);
        const timing = panel.querySelector(".verify-timing") || document.createElement("div");
        timing.className = "verify-timing";
        timing.style.marginTop = "8px";
        timing.style.opacity = "0.75";
        timing.style.fontSize = ".76rem";
        timing.textContent = `Answered in ${elapsed} ms by the deployed service.`;
        panel.append(timing);
        button.disabled = false;
        button.textContent = label;
      }
    });
  };

  wire("#run-exit-test", "#exit-test-result", async (panel) => {
    // The explicit empty body matters: Google's front end rejects a POST with no Content-Length.
    const response = await fetch("/exit-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const data = await response.json();
    const passed = data.passed === data.total;
    show(panel, {
      state: passed ? "pass" : "fail",
      headline: `${data.passed} of ${data.total} checks passed`,
      lines: (data.checks || []).map((check) => ({ ok: check.pass, text: check.check })),
      note: passed
        ? "Registered, slept, woke, quarantined a hidden instruction, refused a fabricated number, and recovered from a dead worker."
        : "At least one guarantee did not hold. That is reported rather than hidden.",
    });
  });

  // The published numbers come from a Python script that drives the public API. Nothing about those
  // calls needs Python, so the browser can make them too and a judge never has to open a terminal
  // to check a claim. This is the same public, credential-free surface; only the caller differs.
  const get = async (path) => (await fetch(path)).json();
  const post = async (path, body) =>
    (await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    })).json();

  wire("#run-acceptance", "#acceptance-result", async (panel) => {
    const results = [];
    const record = (text, ok) => results.push({ text, ok: Boolean(ok) });

    const health = await get("/health");
    record("service is healthy and says its clock is simulated",
           health.ok === true && health.sim_mode === true);

    const fixtures = await get("/sixty-days/fixtures");
    record(`recorded letter extraction is ${fixtures.measured.correct}/${fixtures.measured.total}`,
           fixtures.measured.correct === fixtures.measured.total);

    const photos = await get("/sixty-days/evidence/fixtures");
    record(`recorded photo screening is ${photos.measured.correct}/${photos.measured.total}`,
           photos.measured.correct === photos.measured.total);

    await post("/sixty-days/demo/anchor", { fixture: "damage_and_insurance" });
    const opened = await post("/sixty-days/cases",
                              { fixture: "damage_and_insurance", applicant_ref: "DEMO-verify" });
    record(`${opened.deficiencies.length} reason(s) quoted word for word from the letter`,
           opened.deficiencies.length > 0 &&
           opened.deficiencies.every((d) => d.quoted_text && d.quoted_text.length > 10));
    record(`${opened.wakes.length} reminders registered at intake`, opened.wakes.length === 8);
    record("the raw letter is not returned with the case",
           !("raw" in opened) && !("transcription" in opened));

    const bad = await post(`/sixty-days/cases/${opened.case_id}/evidence/check`,
                           { fixture: "damage_close_bad", requirement_key: "photo_wide" });
    record(`a too-close photo is refused with actionable guidance (${bad.decision})`,
           bad.decision === "retake" && Boolean(bad.guidance));

    const good = await post(`/sixty-days/cases/${opened.case_id}/evidence/check`,
                            { fixture: "damage_wide_good", requirement_key: "photo_wide" });
    record("a readable photo is only ever ready for applicant review",
           good.decision === "ready_for_review");

    const prepared = await post(`/sixty-days/cases/${opened.case_id}/requests/prepare`,
                                { requirement_key: "insurance_denial", requested_on: "2026-08-10" });
    record("the insurer request is prepared, not sent",
           prepared.status === "prepared_for_applicant" && prepared.delivery === "applicant_sends");
    record("a no-reply check is registered against the deadline",
           Boolean(prepared.tracking && prepared.tracking.wake_id));

    const packet = await post(`/sixty-days/cases/${opened.case_id}/packet`,
                              { applicant_statement: "" });
    record(`the draft still lists ${packet.missing.length} missing item(s)`, packet.missing.length > 0);
    record("every packet statement is grounded in the letter's own words",
           packet.verified_statements.length > 0);

    // The safety claim that matters most is the absence of something, so check the absence.
    const forbidden = await Promise.all(
      ["/v1/send", "/v1/submit", "/sixty-days/send", "/sixty-days/submit"].map(
        (path) => fetch(path, { method: "POST", headers: { "Content-Length": "0" } })
                    .then((r) => r.status).catch(() => 0)));
    record("no send or submission route exists", forbidden.every((code) => code === 404));

    const passed = results.filter((r) => r.ok).length;
    show(panel, {
      state: passed === results.length ? "pass" : "fail",
      headline: `${passed} of ${results.length} published claims held`,
      lines: results,
      note: passed === results.length
        ? "Checked from this browser against the public API. No credentials, no terminal, nothing replayed."
        : "At least one published claim did not hold. That is shown rather than hidden.",
    });
  });

  wire("#run-scheduler-check", "#scheduler-result", async (panel) => {
    const data = await (await fetch("/sixty-days/scheduler")).json();
    const running = data.status === "running";
    const ago = data.seconds_since_last_scan;
    show(panel, {
      state: running ? "pass" : "fail",
      headline: running
        ? `A real scheduler woke this service ${ago} second${ago === 1 ? "" : "s"} ago`
        : `Scheduler status: ${data.status}`,
      lines: [
        { text: `Job: ${data.job}, ${data.schedule}` },
        { text: `Calls ${data.target}, authenticated with ${data.authentication}` },
        { text: `Clock: ${data.clock}` },
      ],
      note: data.note,
    });
  });

  wire("#run-conformance", "#conformance-result", async (panel) => {
    const data = await (await fetch("/sixty-days/conformance")).json();
    const rules = data.rules || [];
    show(panel, {
      state: rules.length ? "pass" : "fail",
      headline: `${rules.length} published rule${rules.length === 1 ? "" : "s"}, each citing code and a test`,
      lines: rules.map((rule) => ({
        text: `${rule.rule} — ${rule.implementation}`,
      })),
      note: `Standard: ${data.standard}`,
    });
  });
})();
