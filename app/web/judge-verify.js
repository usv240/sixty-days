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
