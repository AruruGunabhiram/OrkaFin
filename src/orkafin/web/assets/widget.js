import { createAssistantRenderer } from "./widget-renderer.js";
import { createAssistantState } from "./widget-state.js";
import { createAssistantTransport } from "./widget-transport.js";

export function mountAssistantWidget(root, { context, transport, document = window.document } = {}) {
  if (!root) throw new Error("An assistant root element is required.");
  const state = createAssistantState(context || { app_id: "orka_ats", page: "dashboard" });
  const client = transport || createAssistantTransport();
  let conversationId = null;

  async function sendQuestion(rawQuestion) {
    const question = rawQuestion.trim();
    if (!question || state.getSnapshot().isSending) return;
    state.beginRequest(question);
    try {
      const result = await client.query({
        question,
        context: state.getSnapshot().context,
        conversationId,
      });
      conversationId = result.conversation_id || conversationId;
      state.receive(result);
    } catch (error) {
      state.fail(error);
    }
  }

  const unsubscribe = createAssistantRenderer({
    document,
    root,
    state,
    onSend: sendQuestion,
    onReset: () => {
      conversationId = null;
      state.reset();
    },
  });
  return {
    open: () => state.open(),
    close: () => state.close(),
    setContext: (context) => state.setContext(context),
    reset: () => {
      conversationId = null;
      state.reset();
    },
    destroy: () => {
      unsubscribe();
      root.replaceChildren();
    },
  };
}
