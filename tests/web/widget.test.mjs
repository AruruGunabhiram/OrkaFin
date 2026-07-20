import assert from "node:assert/strict";
import test from "node:test";

import { mountAssistantWidget } from "../../src/orkafin/web/assets/widget.js";
import { renderAssistantResponse } from "../../src/orkafin/web/assets/widget-renderer.js";
import { AssistantTransportError } from "../../src/orkafin/web/assets/widget-transport.js";

class FakeElement {
  constructor(document, tagName) {
    this.document = document;
    this.tagName = tagName;
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.textContent = "";
    this.className = "";
    this.hidden = false;
    this.value = "";
    this.disabled = false;
  }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; this.textContent = ""; }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  dispatch(type, extras = {}) {
    this.listeners[type]?.({ key: extras.key, preventDefault() {} });
  }
  focus() { this.document.activeElement = this; }
}

class FakeDocument {
  constructor() { this.activeElement = null; }
  createElement(tagName) { return new FakeElement(this, tagName); }
}

function findText(node, text) {
  if (node.textContent === text) return node;
  for (const child of node.children) {
    const result = findText(child, text);
    if (result) return result;
  }
  return null;
}

function flatten(node) {
  return [node, ...node.children.flatMap(flatten)];
}

function findClass(node, className) {
  return flatten(node).find((candidate) => candidate.className === className) || null;
}

test("renders response text as text nodes rather than markup", () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  renderAssistantResponse(document, root, {
    request_id: "request-safe",
    content: {
      kind: "unavailable_information",
      text: "<img src=x onerror=alert(1)>",
      reason_code: "source_missing",
    },
    sources: [{ source_id: "safe", title: "Safe source", uncertainty_reason: "Revision pending." }],
  });

  assert.ok(findText(root, "<img src=x onerror=alert(1)>"));
  assert.ok(findText(root, "Reason: source_missing"));
  assert.ok(findText(root, " Uncertainty: Revision pending."));
  assert.equal(flatten(root).some((node) => node.tagName === "img"), false);
});

test("suggested prompt dispatches the selected candidate as untrusted context", async () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  let request = null;
  const widget = mountAssistantWidget(root, {
    document,
    context: {
      app_id: "orka_ats",
      page: "candidate_profile",
      selected_entity: { type: "candidate", id: "CAND-1042" },
    },
    transport: {
      async query(value) {
        request = value;
        return {
          conversation_id: "conversation-local",
          request_id: "request-local",
          content: { kind: "verified_fact", text: "Authorized synthetic summary." },
          sources: [],
        };
      },
    },
  });

  widget.open();
  findText(root, "Summarize this candidate").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(request.question, "Summarize this candidate");
  assert.deepEqual(request.context.selected_entity, { type: "candidate", id: "CAND-1042" });
  assert.equal(Object.hasOwn(request.context, "permissions"), false);
});

test("renders refusals, sources, and safe API failures", async () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  const widget = mountAssistantWidget(root, {
    document,
    context: { app_id: "orka_ats", page: "candidate_profile" },
    transport: {
      async query() {
        return {
          conversation_id: "conversation-local",
          request_id: "request-refusal",
          content: { kind: "refusal", text: "Access was not verified." },
          sources: [{ source_id: "policy", title: "Access policy", excerpt: "Synthetic policy." }],
        };
      },
    },
  });
  widget.open();
  findText(root, "Explain this page").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(findText(root, "Request unavailable"));
  assert.ok(findText(root, "Sources"));
  assert.ok(findText(root, "Access policy"));

  const errorRoot = document.createElement("div");
  const errorWidget = mountAssistantWidget(errorRoot, {
    document,
    context: { app_id: "orka_ats", page: "dashboard" },
    transport: { async query() { throw new AssistantTransportError("adapter_failure", "Adapter unavailable.", "request-error"); } },
  });
  errorWidget.open();
  findText(errorRoot, "What can I do here?").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(findText(errorRoot, "OrkaATS adapter unavailable"));
  assert.ok(findText(errorRoot, "Adapter unavailable."));
});

test("previews, confirms, and executes only after a separate explicit click", async () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  const challenge = "challenge_plaintext_must_not_render_1234567890";
  let proposedRequest = null;
  let confirmationRequest = null;
  let executionRequest = null;
  const widget = mountAssistantWidget(root, {
    document,
    context: {
      app_id: "orka_ats",
      page: "candidate_profile",
      selected_entity: { type: "candidate", id: "CAND-1042" },
    },
    transport: {
      async proposeAction(value) {
        proposedRequest = value;
        return {
          proposal_id: "proposal-widget",
          preview: {
            summary: "Prepare a candidate start-date update for confirmation.",
            owning_app_id: "orka_ats",
            owning_app_display_name: "Mock OrkaATS",
            target_candidate_id: "CAND-1042",
            affected_user_id: "mock-user-admin",
            affected_user_display_name: "Synthetic Administrator",
            affected_workspace_id: "workspace_recruiting_alpha",
            affected_workspace_display_name: "Synthetic Recruiting Alpha",
            changes: [{ field_label: "Start date", old_value: "2026-08-17", new_value: "2026-10-06" }],
            warnings: ["No candidate change will be made."],
            reversible: true,
          },
          confirmation: { confirmation_token: challenge },
        };
      },
      async confirmAction(value) {
        confirmationRequest = value;
        return {
          proposal_status: "confirmed",
          confirmation_status: "accepted",
          execution_ready: true,
          execution_enabled: true,
          execution_state: "ready",
          message: "Confirmation accepted. No action has been executed yet.",
        };
      },
      async executeAction(value) {
        executionRequest = value;
        return {
          execution: {
            status: "succeeded",
            safe_message: "Mock OrkaATS confirmed the candidate start date was updated.",
            idempotency_key: "action-widget-idempotency-0001",
          },
          idempotent_replay: false,
        };
      },
    },
  });

  widget.open();
  const dateInput = findClass(root, "assistant-action-date");
  dateInput.value = "2026-10-06";
  findClass(root, "assistant-action-form").dispatch("submit");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(proposedRequest.startDate, "2026-10-06");
  assert.deepEqual(proposedRequest.context.selected_entity, { type: "candidate", id: "CAND-1042" });
  assert.ok(findText(root, "Mock execution only — real OrkaATS and its Google Sheet are not connected."));
  assert.ok(findText(root, "Start date: 2026-08-17 → 2026-10-06"));
  assert.equal(findText(root, challenge), null);

  findText(root, "Confirm update").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(confirmationRequest.decision, "accept");
  assert.equal(confirmationRequest.confirmationToken, challenge);
  assert.equal(confirmationRequest.startDate, "2026-10-06");
  assert.equal(executionRequest, null);
  assert.ok(findText(root, "Confirmation accepted. No action has been executed yet."));
  assert.ok(findText(root, "Execute approved update"));
  assert.equal(findText(root, challenge), null);

  findText(root, "Execute approved update").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(executionRequest.proposalId, "proposal-widget");
  assert.deepEqual(executionRequest.context.selected_entity, { type: "candidate", id: "CAND-1042" });
  assert.ok(findText(root, "Mock OrkaATS confirmed the candidate start date was updated."));
});

test("execution timeout never claims that no change occurred or offers a retry", async () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  const widget = mountAssistantWidget(root, {
    document,
    context: {
      app_id: "orka_ats",
      page: "candidate_profile",
      selected_entity: { type: "candidate", id: "CAND-1042" },
    },
    transport: {
      async proposeAction() {
        return {
          proposal_id: "proposal-timeout",
          preview: {
            summary: "Preview",
            owning_app_id: "orka_ats",
            owning_app_display_name: "Mock OrkaATS",
            target_candidate_id: "CAND-1042",
            affected_user_id: "mock-user-admin",
            affected_workspace_id: "workspace_recruiting_alpha",
            changes: [{ field_label: "Start date", old_value: "2026-08-17", new_value: "2026-10-06" }],
            warnings: ["Mock only."],
            reversible: true,
          },
          confirmation: { confirmation_token: "timeout_challenge_plaintext_1234567890123456" },
        };
      },
      async confirmAction() {
        return {
          proposal_status: "confirmed",
          confirmation_status: "accepted",
          execution_ready: true,
          execution_enabled: true,
          execution_state: "ready",
          message: "Confirmation accepted. No action has been executed yet.",
        };
      },
      async executeAction() {
        throw new AssistantTransportError("timeout", "The request timed out.");
      },
    },
  });

  widget.open();
  findClass(root, "assistant-action-date").value = "2026-10-06";
  findClass(root, "assistant-action-form").dispatch("submit");
  await new Promise((resolve) => setImmediate(resolve));
  findText(root, "Confirm update").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));
  findText(root, "Execute approved update").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));

  assert.ok(findText(root, "OrkaATS did not confirm the outcome. Do not retry; reconcile by idempotency key."));
  assert.equal(findText(root, "Execute approved update"), null);
  assert.equal(flatten(root).some((node) => node.textContent.includes("No changes were made")), false);
});

test("cancel control rejects the issued confirmation instead of executing", async () => {
  const document = new FakeDocument();
  const root = document.createElement("div");
  let decision = null;
  const widget = mountAssistantWidget(root, {
    document,
    context: {
      app_id: "orka_ats",
      page: "candidate_profile",
      selected_entity: { type: "candidate", id: "CAND-1042" },
    },
    transport: {
      async proposeAction() {
        return {
          proposal_id: "proposal-cancel",
          preview: {
            summary: "Preview",
            owning_app_id: "orka_ats",
            owning_app_display_name: "Mock OrkaATS",
            target_candidate_id: "CAND-1042",
            affected_user_id: "mock-user-admin",
            affected_workspace_id: "workspace_recruiting_alpha",
            changes: [{ field_label: "Start date", old_value: "2026-08-17", new_value: "2026-10-06" }],
            warnings: ["Mock only."],
            reversible: true,
          },
          confirmation: { confirmation_token: "cancel_challenge_plaintext_123456789012345678" },
        };
      },
      async confirmAction(value) {
        decision = value.decision;
        return {
          proposal_status: "cancelled",
          confirmation_status: "rejected",
          execution_ready: false,
          execution_enabled: false,
          execution_state: "not_started",
          message: "Confirmation was cancelled. No action was executed.",
        };
      },
    },
  });

  widget.open();
  findClass(root, "assistant-action-date").value = "2026-10-06";
  findClass(root, "assistant-action-form").dispatch("submit");
  await new Promise((resolve) => setImmediate(resolve));
  findText(root, "Cancel").dispatch("click");
  await new Promise((resolve) => setImmediate(resolve));

  assert.equal(decision, "reject");
  assert.ok(findText(root, "Confirmation was cancelled. No action was executed."));
});
