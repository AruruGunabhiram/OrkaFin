import { createAssistantRenderer } from "./widget-renderer.js";
import { createAssistantState } from "./widget-state.js";
import { createAssistantTransport } from "./widget-transport.js";

export function mountAssistantWidget(root, { context, transport, document = window.document } = {}) {
  if (!root) throw new Error("An assistant root element is required.");
  const state = createAssistantState(context || { app_id: "orka_ats", page: "dashboard" });
  const client = transport || createAssistantTransport();
  let conversationId = null;

  async function evaluateRecommendations() {
    try {
      const result = await client.evaluateRecommendations({ context: state.getSnapshot().context });
      state.receiveRecommendation(result);
    } catch (_) {
      // Recommendation availability must never make the assistant panel noisy or unusable.
    }
  }

  async function submitRecommendationFeedback(feedbackType, preference) {
    const recommendation = state.getSnapshot().recommendation;
    if (!recommendation) return;
    try {
      const result = await client.submitFeedback({
        recommendationId: recommendation.recommendation_id,
        feedbackType,
        context: state.getSnapshot().context,
        preference,
      });
      state.feedbackReceived(result);
    } catch (error) {
      state.fail(error);
    }
  }

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
    onFeedback: submitRecommendationFeedback,
    onReset: () => {
      conversationId = null;
      state.reset();
    },
  });
  void evaluateRecommendations();
  return {
    open: () => state.open(),
    close: () => state.close(),
    setContext: (context) => {
      state.setContext(context);
      void evaluateRecommendations();
    },
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
