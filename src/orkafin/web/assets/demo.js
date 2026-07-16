import { mountAssistantWidget } from "./widget.js";
import { createAssistantTransport } from "./widget-transport.js";

const root = document.querySelector("#orkafin-assistant");
const page = document.querySelector("#demo-page");
const candidate = document.querySelector("#demo-candidate");
const widget = mountAssistantWidget(root, {
  context: contextFromControls(),
  transport: createAssistantTransport({ baseUrl: root.dataset.apiBaseUrl }),
});

function contextFromControls() {
  const selectedEntity = candidate.value ? { type: "candidate", id: candidate.value } : null;
  return { app_id: "orka_ats", page: page.value, selected_entity: selectedEntity };
}

function updateContext() {
  widget.setContext(contextFromControls());
}

page.addEventListener("change", updateContext);
candidate.addEventListener("change", updateContext);
