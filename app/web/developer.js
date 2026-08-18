(() => {
  "use strict";

  const form = document.querySelector("#key-form");
  const status = document.querySelector("#developer-status");
  const result = document.querySelector("#key-result");
  const keyOutput = document.querySelector("#api-key");
  const expires = document.querySelector("#key-expires");
  const curl = document.querySelector("#curl-example");
  const copyButton = document.querySelector("#copy-key");
  const testButton = document.querySelector("#test-key");
  const revokeButton = document.querySelector("#revoke-key");
  const theme = document.querySelector("#theme-toggle");
  let apiKey = "";

  const setStatus = (message, kind = "neutral") => {
    status.textContent = message;
    status.dataset.kind = kind;
  };

  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
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

  const curlTemplate = curl.textContent.replaceAll("SERVICE_URL", window.location.origin);
  curl.textContent = curlTemplate;

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
      apiKey = body.api_key;
      keyOutput.value = apiKey;
      expires.textContent = new Date(body.expires_at).toLocaleString();
      curl.textContent = curlTemplate.replaceAll("YOUR_API_KEY", apiKey);
      result.hidden = false;
      form.elements.invitation_code.value = "";
      setStatus("Your key is ready. Save it now because it will not be shown again.", "success");
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

  testButton.addEventListener("click", async () => {
    if (!apiKey) return;
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
    if (!apiKey) return;
    revokeButton.disabled = true;
    setStatus("Revoking the key...", "neutral");
    try {
      const response = await fetch("/v1/key", {
        method: "DELETE",
        headers: {"X-API-Key": apiKey},
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.detail || "The key could not be revoked.");
      apiKey = "";
      keyOutput.value = "";
      result.hidden = true;
      setStatus("The key has been revoked and can no longer call the API.", "success");
    } catch (error) {
      setStatus(error.message, "error");
      revokeButton.disabled = false;
    }
  });

  theme.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme !== "dark";
    root.dataset.theme = dark ? "dark" : "light";
    theme.textContent = dark ? "Use light mode" : "Use dark mode";
    theme.setAttribute("aria-pressed", String(dark));
  });
})();
