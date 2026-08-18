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

  const renderExamples = () => {
    const visibleKey = apiKey || "YOUR_API_KEY";
    for (const [node, template] of templates) {
      node.textContent = template.replaceAll("YOUR_API_KEY", visibleKey);
    }
  };

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
      document.querySelector("#access-mode").textContent =
        config.issuance === "invite_only" ? "Invite-only issuance is live" : "Issuance is disabled";
      document.querySelector("#key-lifetime").textContent = config.ttl_hours + " hour lifetime";
      form.querySelector("button[type=submit]").disabled = config.issuance !== "invite_only";
    })
    .catch(() => setStatus("Access configuration could not be loaded.", "error"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = form.querySelector("button[type=submit]");
    submit.disabled = true;
    setStatus("Creating a scoped key...", "neutral");
    const data = new FormData(form);
    const payload = {
      invitation_code: data.get("invitation_code"),
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
      form.elements.invitation_code.value = "";
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
    button.addEventListener("click", async () => {
      const target = document.querySelector(button.dataset.copyCode);
      const copied = await copy(target.textContent);
      button.textContent = copied ? "Copied" : "Select and copy";
      window.setTimeout(() => { button.textContent = "Copy request"; }, 1600);
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
