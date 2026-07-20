export const SUGGESTED_PROMPTS = [
  "Explain this page",
  "What can I do here?",
  "Summarize this candidate",
  "Recommend a useful feature",
];

export function createAssistantState(initialContext) {
  let snapshot = {
    isOpen: false,
    isSending: false,
    question: "",
    context: { ...initialContext },
    response: null,
    recommendation: null,
    recommendationNotice: "",
    error: null,
    status: "Assistant closed.",
  };
  const listeners = new Set();

  function publish(update) {
    snapshot = { ...snapshot, ...update };
    listeners.forEach((listener) => listener(snapshot));
  }

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      listener(snapshot);
      return () => listeners.delete(listener);
    },
    open() {
      publish({ isOpen: true, status: "Assistant opened." });
    },
    close() {
      publish({ isOpen: false, status: "Assistant closed." });
    },
    setQuestion(question) {
      publish({ question, error: null });
    },
    setContext(context) {
      publish({ context: { ...context }, error: null });
    },
    beginRequest(question) {
      publish({
        isSending: true,
        question,
        error: null,
        status: "Assistant is preparing a response.",
      });
    },
    receive(response) {
      publish({
        isSending: false,
        question: "",
        response,
        error: null,
        status: "Assistant response received.",
      });
    },
    receiveRecommendation(result) {
      const recommendation = result?.recommendations?.[0] || null;
      const notice = recommendation
        ? "A relevant recommendation is available."
        : result?.suppressed_rule_ids?.length
          ? "A recent recommendation is suppressed."
          : result?.preference === "disabled"
            ? "Recommendations are disabled."
            : "";
      publish({ recommendation, recommendationNotice: notice });
    },
    feedbackReceived(result) {
      const notice = result?.preference === "disabled"
        ? "Recommendations are disabled."
        : result?.suppressed_until
          ? `Dismissed until ${new Date(result.suppressed_until).toLocaleDateString()}.`
          : "Feedback saved.";
      publish({ recommendation: null, recommendationNotice: notice });
    },
    fail(error) {
      publish({ isSending: false, error, status: error.message });
    },
    reset() {
      publish({
        isSending: false,
        question: "",
        response: null,
        error: null,
        status: "Conversation reset.",
      });
    },
  };
}
