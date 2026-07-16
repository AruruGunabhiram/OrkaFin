import { SUGGESTED_PROMPTS } from "./widget-state.js";

function element(document, tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function appendText(document, parent, tag, className, text) {
  const node = element(document, tag, className, text);
  parent.append(node);
  return node;
}

export function renderAssistantResponse(document, container, response) {
  container.replaceChildren();
  if (!response) {
    appendText(document, container, "p", "assistant-empty", "Ask a question to get grounded help.");
    return;
  }
  const content = response.content || {};
  const kindLabel = {
    refusal: "Request unavailable",
    unavailable_information: "Information unavailable",
  }[content.kind];
  if (kindLabel) appendText(document, container, "h3", "assistant-response-kind", kindLabel);
  appendText(document, container, "p", "assistant-response-text", content.text || "No response text was returned.");
  if (content.reason_code) {
    appendText(document, container, "p", "assistant-uncertainty", `Reason: ${content.reason_code}`);
  }
  if (Array.isArray(content.steps) && content.steps.length) {
    const list = element(document, "ol", "assistant-steps");
    content.steps.forEach((step) => appendText(document, list, "li", "", step));
    container.append(list);
  }
  if (Array.isArray(response.sources) && response.sources.length) {
    const sources = element(document, "section", "assistant-sources");
    appendText(document, sources, "h3", "", "Sources");
    const list = element(document, "ul", "");
    response.sources.forEach((source) => {
      const item = element(document, "li", "");
      appendText(document, item, "strong", "", source.title || source.source_id || "Source");
      if (source.excerpt) appendText(document, item, "span", "", ` — ${source.excerpt}`);
      if (source.uncertainty_reason) {
        appendText(document, item, "span", "", ` Uncertainty: ${source.uncertainty_reason}`);
      }
      list.append(item);
    });
    sources.append(list);
    container.append(sources);
  }
  if (response.request_id) appendText(document, container, "p", "assistant-request-id", `Request ID: ${response.request_id}`);
}

export function createAssistantRenderer({ document, root, state, onSend, onReset }) {
  root.replaceChildren();
  const launcher = element(document, "button", "assistant-launcher", "Ask OrkaFin");
  launcher.type = "button";
  launcher.setAttribute("aria-expanded", "false");
  launcher.setAttribute("aria-controls", "orkafin-assistant-panel");
  const panel = element(document, "section", "assistant-panel");
  panel.id = "orkafin-assistant-panel";
  panel.setAttribute("aria-label", "OrkaFin assistant");
  panel.hidden = true;
  const header = element(document, "header", "assistant-header");
  appendText(document, header, "h2", "", "OrkaFin assistant");
  const close = element(document, "button", "assistant-close", "Close");
  close.type = "button";
  header.append(close);
  const response = element(document, "div", "assistant-response");
  response.setAttribute("aria-live", "polite");
  const suggestions = element(document, "div", "assistant-suggestions");
  appendText(document, suggestions, "p", "", "Try a question");
  SUGGESTED_PROMPTS.forEach((prompt) => {
    const button = element(document, "button", "assistant-suggestion", prompt);
    button.type = "button";
    button.addEventListener("click", () => onSend(prompt));
    suggestions.append(button);
  });
  const form = element(document, "form", "assistant-form");
  const label = element(document, "label", "", "Question");
  label.htmlFor = "orkafin-question";
  const input = element(document, "textarea", "assistant-question");
  input.id = "orkafin-question";
  input.name = "question";
  input.maxLength = 500;
  input.rows = 3;
  input.required = true;
  input.placeholder = "Ask about this OrkaATS page";
  const send = element(document, "button", "assistant-send", "Send");
  send.type = "submit";
  form.append(label, input, send);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    onSend(input.value);
  });
  const reset = element(document, "button", "assistant-reset", "Reset conversation");
  reset.type = "button";
  reset.addEventListener("click", onReset);
  const status = element(document, "p", "assistant-status", "");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");
  panel.append(header, response, suggestions, form, reset, status);
  root.append(launcher, panel);

  launcher.addEventListener("click", () => state.open());
  close.addEventListener("click", () => state.close());
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") state.close();
  });
  return state.subscribe((snapshot) => {
    panel.hidden = !snapshot.isOpen;
    launcher.setAttribute("aria-expanded", String(snapshot.isOpen));
    if (snapshot.isOpen && document.activeElement !== input) input.focus();
    if (!snapshot.isOpen && document.activeElement !== launcher) launcher.focus();
    input.value = snapshot.question;
    input.disabled = snapshot.isSending;
    send.disabled = snapshot.isSending;
    send.textContent = snapshot.isSending ? "Sending…" : "Send";
    status.textContent = snapshot.status;
    if (snapshot.error) {
      response.replaceChildren();
      const errorLabel = {
        adapter_failure: "OrkaATS adapter unavailable",
        offline: "Assistant offline",
        timeout: "Request timed out",
      }[snapshot.error.kind] || "Request problem";
      appendText(document, response, "h3", "assistant-response-kind", errorLabel);
      appendText(document, response, "p", "assistant-response-text", snapshot.error.message);
      if (snapshot.error.requestId) appendText(document, response, "p", "assistant-request-id", `Request ID: ${snapshot.error.requestId}`);
    } else {
      renderAssistantResponse(document, response, snapshot.response);
    }
  });
}
