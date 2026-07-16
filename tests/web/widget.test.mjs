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
