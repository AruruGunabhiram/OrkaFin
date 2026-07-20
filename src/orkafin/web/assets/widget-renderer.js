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

function renderRecommendation(document, container, recommendation, notice, onFeedback) {
  container.replaceChildren();
  if (!recommendation) {
    if (notice) appendText(document, container, "p", "assistant-recommendation-notice", notice);
    return;
  }
  appendText(document, container, "h3", "assistant-recommendation-title", recommendation.title);
  appendText(document, container, "p", "assistant-recommendation-body", recommendation.body);
  appendText(document, container, "p", "assistant-recommendation-reason", `Why: ${recommendation.rationale}`);
  if (Array.isArray(recommendation.source_references) && recommendation.source_references.length) {
    appendText(document, container, "p", "assistant-recommendation-source", `Source: ${recommendation.source_references.join(", ")}`);
  }
  const controls = element(document, "div", "assistant-recommendation-controls");
  [
    ["helpful", "Helpful"],
    ["not_helpful", "Not helpful"],
    ["accepted", "Accept"],
    ["dismissed", "Dismiss"],
    ["dismissed", "Disable recommendations", "disabled"],
  ].forEach(([type, label, preference]) => {
    const button = element(document, "button", "assistant-recommendation-action", label);
    button.type = "button";
    button.addEventListener("click", () => onFeedback(type, preference));
    controls.append(button);
  });
  container.append(controls);
}

function renderActionControls(
  document,
  container,
  snapshot,
  onProposeAction,
  onConfirmAction,
  onCancelAction,
  onExecuteAction,
) {
  container.replaceChildren();
  appendText(document, container, "h3", "assistant-action-title", "Mock approved action");
  appendText(
    document,
    container,
    "p",
    "assistant-action-scope",
    "Mock execution only — real OrkaATS and its Google Sheet are not connected.",
  );

  if (snapshot.actionExecution) {
    const resultClass = snapshot.actionExecution.status === "succeeded"
      ? "assistant-action-result"
      : snapshot.actionExecution.status === "unknown"
        ? "assistant-action-unknown"
        : "assistant-action-error";
    appendText(document, container, "p", resultClass, snapshot.actionExecution.safe_message);
    if (snapshot.actionExecution.status === "unknown") {
      appendText(
        document,
        container,
        "p",
        "assistant-action-idempotency",
        `Reconciliation key: ${snapshot.actionExecution.idempotency_key}`,
      );
    }
    return;
  }
  if (snapshot.actionConfirmation) {
    appendText(document, container, "p", "assistant-action-confirmed", snapshot.actionConfirmation.message);
    if (snapshot.executionProposalId) {
      const execute = element(
        document,
        "button",
        "assistant-action-execute",
        snapshot.isActionSending ? "Executing…" : "Execute approved update",
      );
      execute.type = "button";
      execute.disabled = snapshot.isActionSending;
      execute.addEventListener("click", onExecuteAction);
      container.append(execute);
    }
    return;
  }
  if (snapshot.actionError) {
    appendText(document, container, "p", "assistant-action-error", snapshot.actionStatus);
  }

  const proposal = snapshot.actionProposal;
  if (!proposal) {
    const form = element(document, "form", "assistant-action-form");
    const label = element(document, "label", "", "Proposed start date");
    label.htmlFor = "orkafin-start-date";
    const input = element(document, "input", "assistant-action-date");
    input.id = "orkafin-start-date";
    input.name = "start_date";
    input.type = "date";
    input.required = true;
    input.disabled = snapshot.isActionSending;
    const preview = element(
      document,
      "button",
      "assistant-action-preview",
      snapshot.isActionSending ? "Preparing…" : "Preview start-date update",
    );
    preview.type = "submit";
    preview.disabled = snapshot.isActionSending;
    form.append(label, input, preview);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      onProposeAction(input.value);
    });
    container.append(form);
    return;
  }

  const preview = proposal.preview;
  appendText(document, container, "h4", "assistant-action-preview-title", "Review exact preview");
  appendText(document, container, "p", "", preview.summary);
  appendText(document, container, "p", "", `Owning app: ${preview.owning_app_display_name} (${preview.owning_app_id})`);
  appendText(document, container, "p", "", `Target candidate: ${preview.target_candidate_id}`);
  appendText(document, container, "p", "", `Affected user: ${preview.affected_user_display_name || preview.affected_user_id}`);
  appendText(document, container, "p", "", `Affected workspace: ${preview.affected_workspace_display_name || preview.affected_workspace_id}`);
  preview.changes.forEach((change) => {
    appendText(
      document,
      container,
      "p",
      "assistant-action-change",
      `${change.field_label}: ${change.old_value ?? "Not set"} → ${change.new_value}`,
    );
  });
  appendText(document, container, "p", "", `Reversible: ${preview.reversible ? "Yes" : "No"}`);
  const warnings = element(document, "ul", "assistant-action-warnings");
  preview.warnings.forEach((warning) => appendText(document, warnings, "li", "", warning));
  container.append(warnings);
  const controls = element(document, "div", "assistant-action-controls");
  const confirm = element(document, "button", "assistant-action-confirm", "Confirm update");
  confirm.type = "button";
  confirm.disabled = snapshot.isActionSending;
  confirm.addEventListener("click", onConfirmAction);
  const cancel = element(document, "button", "assistant-action-cancel", "Cancel");
  cancel.type = "button";
  cancel.disabled = snapshot.isActionSending;
  cancel.addEventListener("click", onCancelAction);
  controls.append(confirm, cancel);
  container.append(controls);
}

export function createAssistantRenderer({
  document,
  root,
  state,
  onSend,
  onFeedback,
  onProposeAction,
  onConfirmAction,
  onCancelAction,
  onExecuteAction,
  onReset,
}) {
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
  const recommendation = element(document, "section", "assistant-recommendation");
  recommendation.setAttribute("aria-live", "polite");
  const action = element(document, "section", "assistant-action");
  action.setAttribute("aria-live", "polite");
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
  panel.append(header, recommendation, action, response, suggestions, form, reset, status);
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
    renderRecommendation(document, recommendation, snapshot.recommendation, snapshot.recommendationNotice, onFeedback);
    renderActionControls(
      document,
      action,
      snapshot,
      onProposeAction,
      onConfirmAction,
      onCancelAction,
      onExecuteAction,
    );
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
