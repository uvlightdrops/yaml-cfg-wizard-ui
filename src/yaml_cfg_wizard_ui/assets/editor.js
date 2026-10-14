(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const config = JSON.parse(byId("editor-config").textContent);
  const container = byId("fields"), error = byId("error"), status = byId("status");
  let snapshot = null, busy = false, conflict = false;
  const scalar = value => value === null || ["string", "boolean", "number"].includes(typeof value)
    && (typeof value !== "number" || Number.isFinite(value));
  const typeOf = value => value === null ? "null" : typeof value === "number"
    ? (Number.isInteger(value) ? "integer" : "number") : typeof value;
  const display = value => typeof value === "string" ? value : JSON.stringify(value);
  function node(tag, text, parent) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (parent) parent.appendChild(element);
    return element;
  }
  function valid(next) {
    if (!next || typeof next.revision !== "string" || !next.revision || next.revision.length > 1024
      || !Array.isArray(next.rows) || next.rows.length > 1000) throw new Error("snapshot");
    const paths = new Set();
    for (const row of next.rows) {
      if (!row || typeof row.path !== "string" || !row.path || row.path.length > 1024
        || paths.has(row.path) || typeof row.label !== "string" || typeof row.description !== "string"
        || typeof row.overridden !== "boolean" || !scalar(row.override) || !scalar(row.effective)) {
        throw new Error("snapshot");
      }
      paths.add(row.path);
    }
    return next;
  }
  function controls() {
    byId("reload").disabled = busy;
    container.querySelectorAll("input, select, button").forEach(element => {
      element.disabled = busy || conflict || element.dataset.unavailable === "true";
    });
    container.setAttribute("aria-busy", String(busy));
  }
  function render(next) {
    container.replaceChildren();
    next.rows.forEach((row, index) => {
      const spec = Object.hasOwn(config.fields, row.path) ? config.fields[row.path] : {};
      const value = row.overridden ? row.override : row.effective;
      let types = spec.type ? [...spec.type] : value !== null ? [typeOf(value)]
        : row.effective !== null ? [typeOf(row.effective)] : [];
      if (spec.nullable && !types.includes("null")) types.push("null");
      const form = node("form", undefined, container), fieldset = node("fieldset", undefined, form);
      node("legend", row.label, fieldset);
      const description = node("p", row.description, fieldset);
      description.id = `description-${index}`;
      node("p", `Effective: ${display(row.effective)}`, fieldset);
      node("p", row.overridden ? `Override: ${display(row.override)}` : "Override: inherited", fieldset);
      const label = node("label", "Override type", fieldset);
      label.htmlFor = `type-${index}`;
      const select = node("select", undefined, fieldset);
      select.id = label.htmlFor;
      types.forEach(type => {
        const option = node("option", type, select);
        option.value = type;
      });
      const actual = typeOf(value);
      if (types.includes(actual)) select.value = actual;
      else if (actual === "integer" && types.includes("number")) select.value = "number";
      const inputLabel = node("label", "Override value", fieldset);
      inputLabel.htmlFor = `value-${index}`;
      const input = node("input", undefined, fieldset);
      input.id = inputLabel.htmlFor;
      input.setAttribute("aria-describedby", description.id);
      input.value = value === null ? "" : String(value);
      if (spec.maxLength !== undefined) input.maxLength = spec.maxLength;
      function inputMode() {
        input.dataset.unavailable = String(select.value === "null" || !types.length);
        input.hidden = select.value === "null";
        input.inputMode = ["number", "integer"].includes(select.value) ? "decimal" : "text";
        controls();
      }
      select.addEventListener("change", inputMode);
      const save = node("button", "Save override", fieldset);
      save.type = "submit";
      save.dataset.unavailable = String(!types.length);
      select.dataset.unavailable = String(!types.length);
      if (!types.length) node("p", "Editing unavailable: provide explicit scalar type metadata for this null field.", fieldset);
      const remove = node("button", "Remove override (inherit)", fieldset);
      remove.type = "button";
      remove.dataset.unavailable = String(!row.overridden);
      remove.addEventListener("click", () => change(row.path, null, true));
      form.addEventListener("submit", event => {
        event.preventDefault();
        if (busy || conflict || !types.length) return;
        try {
          let edit = input.value;
          switch (select.value) {
            case "null": edit = null; break;
            case "boolean":
              if (!["true", "false"].includes(edit)) throw new Error("Enter true or false.");
              edit = edit === "true"; break;
            case "integer":
            case "number":
              if (!/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(edit)) {
                throw new Error("Enter a finite JSON number.");
              }
              edit = Number(edit);
              if (!Number.isFinite(edit) || select.value === "integer" && !Number.isSafeInteger(edit)) {
                throw new Error("Enter a finite number (integers must be safely representable).");
              }
              break;
          }
          if (typeof edit === "string" && spec.maxLength !== undefined && edit.length > spec.maxLength) {
            throw new Error("Value exceeds the maximum length.");
          }
          void change(row.path, edit, false);
        } catch (failure) {
          error.textContent = failure.message;
        }
      });
      inputMode();
    });
    controls();
  }
  function failure(response) {
    if (response.status === 409) {
      conflict = true;
      return "Configuration changed. Reload explicitly before saving; your draft and revision were retained.";
    }
    if ([401, 403].includes(response.status)) return "Authentication or CSRF failed. Log in again and reload this editor page.";
    if ([400, 422].includes(response.status)) return "Validation failed. Check the value; no edit was accepted.";
    if (response.status === 503) return "Editor busy or runtime unavailable. Retry or contact the operator.";
    return `Configuration request failed (HTTP ${response.status}).`;
  }
  async function request(body) {
    if (busy || body && (!snapshot || conflict)) return;
    busy = true;
    error.textContent = "";
    status.textContent = body ? "Saving override..." : "Loading configuration...";
    controls();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(config.endpoint, {
        method: body ? "POST" : "GET", credentials: "same-origin", cache: "no-store",
        redirect: "error", signal: controller.signal,
        headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": config.csrfToken } : {},
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (!response.ok) {
        error.textContent = failure(response);
        return;
      }
      const next = valid(await response.json());
      snapshot = next;
      conflict = false;
      render(next);
      if (body) byId("saved").textContent = config.savedMessage;
    } catch (failure) {
      error.textContent = failure.message === "snapshot" || failure instanceof SyntaxError
        ? "Invalid snapshot response. Contact the operator; the previous revision was retained."
        : "Configuration request failed or timed out. Check connectivity and reload.";
    } finally {
      clearTimeout(timer);
      busy = false;
      status.textContent = "";
      controls();
    }
  }
  function change(path, value, remove) {
    if (!snapshot) return;
    return request({ revision: snapshot.revision, changes: remove ? {} : { [path]: value },
      remove: remove ? [path] : [] });
  }
  document.title = config.title;
  byId("editor-title").textContent = config.title;
  byId("editor-description").textContent = config.description;
  byId("reload").addEventListener("click", () => request());
  document.documentElement.dataset.configEditor = "ready";
  if (window.parent !== window) window.parent.postMessage({ type: "config-editor-ready" }, window.location.origin);
  void request();
})();
