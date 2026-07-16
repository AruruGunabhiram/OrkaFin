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
