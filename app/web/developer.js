(() => {
  "use strict";

  const form = document.querySelector("#key-form");
  const status = document.querySelector("#developer-status");
  const statusMirror = document.querySelector("#connection-status");
  const result = document.querySelector("#key-result");
  const keyOutput = document.querySelector("#api-key");
  const activeKeyInput = document.querySelector("#active-api-key");
  const expires = document.querySelector("#key-expires");
  const connectionCode = document.querySelector("#curl-example code");
  const workflowCode = document.querySelector("#workflow-example code");
  const copyButton = document.querySelector("#copy-key");
  const useKeyButton = document.querySelector("#use-key");
  const clearKeyButton = document.querySelector("#clear-key");
  const testButton = document.querySelector("#test-key");
  const revokeButton = document.querySelector("#revoke-key");
  const theme = document.querySelector("#theme-toggle");
  let apiKey = "";

  const templates = new Map([
    [connectionCode, connectionCode.textContent.replaceAll("SERVICE_URL", window.location.origin)],
    [workflowCode, workflowCode.textContent.replaceAll("SERVICE_URL", window.location.origin)],
  ]);

  const setStatus = (message, kind = "neutral") => {
    status.textContent = message;
    status.dataset.kind = kind;
    statusMirror.textContent = message;
    statusMirror.dataset.kind = kind;
  };

  // The page tells people not to put the key in screenshots or videos, then used to print it into
  // the example. Show a mask; put the real value on the clipboard.
  const maskKey = (value) =>
    value ? `${value.slice(0, 8)}${"\u2022".repeat(24)}` : "YOUR_API_KEY";

  const renderExamples = () => {
    for (const [node, template] of templates) {
      node.textContent = template.replaceAll("YOUR_API_KEY", maskKey(apiKey));
    }
  };

  const realRequest = (node) =>
    (templates.get(node) || "").replaceAll("YOUR_API_KEY", apiKey || "YOUR_API_KEY");

  const setActiveKey = (value) => {
    apiKey = String(value || "").trim();
    activeKeyInput.value = apiKey;
    renderExamples();
  };

  const copy = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      const copied = document.execCommand("copy");
      area.remove();
      return copied;
    }
  };

  fetch("/developer/config")
    .then((response) => response.ok ? response.json() : Promise.reject())
    .then((config) => {
      const modeLabel = {
        open: "Self-serve issuance is live",
        invite_only: "Invite-only issuance is live",
      };
      document.querySelector("#access-mode").textContent =
        modeLabel[config.issuance] || "Issuance is disabled";
      document.querySelector("#key-lifetime").textContent = config.ttl_hours + " hour lifetime";
      form.querySelector("button[type=submit]").disabled =
        config.issuance !== "open" && config.issuance !== "invite_only";

      // The cap is read from the service rather than written into the page, so the number a
      // visitor is told is the number this deployment actually enforces.
      const help = document.querySelector("#issuance-help");
      if (help) {
        if (config.issuance === "open") {
          help.textContent = config.keys_per_day
            ? `No invitation code is needed. Up to ${config.keys_per_day} keys per day from one address; each expires on its own and can be revoked.`
            : "No invitation code is needed. Each key expires on its own and can be revoked.";
        } else if (config.issuance === "invite_only") {
          help.textContent = "This deployment requires an invitation code from the project owner.";
        } else {
          help.textContent = "Key issuance is disabled on this deployment.";
        }
      }
    })
    .catch(() => setStatus("Access configuration could not be loaded.", "error"));

  // --- Running the example from the page ------------------------------------------------
  // A request you can read is good; a request you can watch return is better, and it is the only
  // way to show that the documented example actually works rather than merely looking plausible.

  const showResponse = (panel, { status, note, body, error }) => {
    panel.replaceChildren();
    panel.classList.toggle("is-error", Boolean(error) || (status && status >= 400));
    const head = document.createElement("div");
    head.className = "response-head";
    const badge = document.createElement("span");
    badge.className = "response-status";
    badge.textContent = error ? "no response" : `HTTP ${status}`;
    head.append(badge);
    if (note) {
      const detail = document.createElement("span");
      detail.className = "response-note";
      detail.textContent = note;
      head.append(detail);
    }
    panel.append(head);
    const pre = document.createElement("pre");
    pre.textContent = body;
    panel.append(pre);
    panel.hidden = false;
  };

  const explain = (status, payload) => {
    if (status === 401) return "The key is missing, expired, or already revoked. Generate a new one above.";
    if (status === 429) return "The daily allowance for this address is spent. It resets at 00:00 UTC.";
    if (status === 422) {
      const detail = typeof payload?.detail === "string" ? payload.detail : "";
      if (detail.includes("Model Armor")) return "Blocked before the model saw it: the text looked like a prompt injection.";
      if (detail.includes("identifier")) return "Refused: the text still contains a direct identifier.";
      return "The request did not match the documented contract.";
    }
    if (status === 503) return "The service could not complete the call. Nothing was stored.";
    if (status >= 200 && status < 300) return "Nothing was sent to anyone, and no case was created for another tenant.";
    return "";
  };

  const runExample = async (button, panel, request) => {
    if (!apiKey) {
      showResponse(panel, {
        error: true, body: "No API key is loaded in this page session.",
        note: "Generate one above, or paste an existing key and press Use this key.",
      });
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Running\u2026";
    const started = performance.now();
    try {
      const response = await fetch(request.path, {
        method: request.method,
        headers: { "X-API-Key": apiKey, ...(request.body ? { "Content-Type": "application/json" } : {}) },
        body: request.body ? JSON.stringify(request.body) : undefined,
      });
      const text = await response.text();
      let payload = null;
      let pretty = text;
      try {
        payload = JSON.parse(text);
        pretty = JSON.stringify(payload, null, 2);
      } catch {
        // A non-JSON body is still worth showing verbatim rather than swallowing.
      }
      const elapsed = Math.round(performance.now() - started);
      showResponse(panel, {
        status: response.status,
        note: `${elapsed} ms \u00b7 ${explain(response.status, payload)}`,
        body: pretty.length > 4000 ? `${pretty.slice(0, 4000)}\n\u2026 truncated for display` : pretty,
      });
    } catch (error) {
      showResponse(panel, {
        error: true,
        body: String(error && error.message ? error.message : error),
        note: "The request never reached the service. Check the connection and try again.",
      });
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  };

  const runConnection = document.querySelector("#run-connection");
  if (runConnection) {
    runConnection.addEventListener("click", () =>
      runExample(runConnection, document.querySelector("#connection-response"), {
        method: "GET", path: "/v1",
      }));
  }

  const runWorkflow = document.querySelector("#run-workflow");
  if (runWorkflow) {
    runWorkflow.addEventListener("click", () =>
      runExample(runWorkflow, document.querySelector("#workflow-response"), {
        method: "POST",
        path: "/v1/cases",
        // Exactly the body printed above, so what runs is what a reader was told to expect.
        body: {
          applicant_ref: "SUBJECT-101",
          disaster_ref: "DR-101",
          acknowledge_deidentified: true,
          document: [
            "DISASTER ASSISTANCE DETERMINATION - SYNTHETIC DEMONSTRATION",
            "Date: August 5, 2026",
            "Decision: Some requested assistance is not approved.",
            "The inspection did not show disaster-caused damage that made the home unsafe to occupy.",
            "We also need the insurance settlement or denial before we can consider uninsured losses.",
            "Your appeal must be received by October 4, 2026.",
          ].join("\n"),
        },
      }));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    setStatus("Creating a scoped key...", "neutral");
    const data = new FormData(form);
    const invitation = data.get("invitation_code");
    const payload = {
      // Omitted entirely when the field is not on the page, so open issuance sends no null secret.
      ...(invitation ? { invitation_code: invitation } : {}),
      tenant_id: String(data.get("tenant_id")).trim().toLowerCase(),
      label: String(data.get("label")).trim(),
      acknowledge_terms: data.get("acknowledge_terms") === "on",
    };
    try {
      const response = await fetch("/developer/keys", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The key could not be created.");
      setActiveKey(body.api_key);
      keyOutput.value = body.api_key;
      expires.textContent = new Date(body.expires_at).toLocaleString();
      result.hidden = false;
      if (form.elements.invitation_code) form.elements.invitation_code.value = "";
      setStatus("Key created and loaded into this browser session. Save it now.", "success");
      keyOutput.focus();
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      submit.disabled = false;
    }
  });

  copyButton.addEventListener("click", async () => {
    if (!apiKey) return;
    setStatus(await copy(apiKey) ? "API key copied." : "Copy failed. Select the key manually.",
      "success");
  });

  useKeyButton.addEventListener("click", () => {
    const value = activeKeyInput.value.trim();
    if (!value) {
      setStatus("Paste an API key before continuing.", "error");
      activeKeyInput.focus();
      return;
    }
    setActiveKey(value);
    setStatus("Key loaded for this page session. It has not been stored in the browser.", "success");
  });

  clearKeyButton.addEventListener("click", () => {
    setActiveKey("");
    keyOutput.value = "";
    result.hidden = true;
    setStatus("The key was cleared from this page session.", "success");
  });

  testButton.addEventListener("click", async () => {
    if (!apiKey) {
      setStatus("Create or load an API key before testing the connection.", "error");
      activeKeyInput.focus();
      return;
    }
    testButton.disabled = true;
    setStatus("Testing the key against this service...", "neutral");
    try {
      const response = await fetch("/v1", {headers: {"X-API-Key": apiKey}});
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The API rejected the key.");
      setStatus("Connection verified for tenant " + body.tenant + ".", "success");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      testButton.disabled = false;
    }
  });

  revokeButton.addEventListener("click", async () => {
    if (!apiKey) {
      setStatus("Create or load an API key before revoking it.", "error");
      return;
    }
    revokeButton.disabled = true;
    setStatus("Revoking the key...", "neutral");
    try {
      const response = await fetch("/v1/key", {
        method: "DELETE",
        headers: {"X-API-Key": apiKey},
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The key could not be revoked.");
      setActiveKey("");
      keyOutput.value = "";
      result.hidden = true;
      setStatus("The key was revoked, cleared, and removed from both examples.", "success");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      revokeButton.disabled = false;
    }
  });

  document.querySelectorAll("[data-copy-code]").forEach((button) => {
    const label = button.textContent;
    button.addEventListener("click", async () => {
      const target = document.querySelector(button.dataset.copyCode);
      // The block on screen shows a masked key. What lands on the clipboard has to be the request
      // that actually runs, or "copy" hands the reader something that fails.
      const copied = await copy(realRequest(target) || target.textContent);
      button.textContent = copied ? "Copied" : "Select and copy";
      window.setTimeout(() => { button.textContent = label; }, 1600);
    });
  });

  theme.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme !== "dark";
    root.dataset.theme = dark ? "dark" : "light";
    theme.textContent = dark ? "Use light mode" : "Use dark mode";
    theme.setAttribute("aria-pressed", String(dark));
  });

  renderExamples();
})();
