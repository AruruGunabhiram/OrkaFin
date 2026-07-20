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
    isActionSending: false,
    actionProposal: null,
    actionConfirmation: null,
    actionExecution: null,
    executionProposalId: null,
    actionError: null,
    actionStatus: "One mock-only start-date action is available after confirmation.",
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
      publish({
        context: { ...context },
        actionProposal: null,
        actionConfirmation: null,
        actionExecution: null,
        executionProposalId: null,
        actionError: null,
        actionStatus: "Context changed. Any prior confirmation challenge was cleared.",
        error: null,
      });
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
    beginActionProposal() {
      publish({
        isActionSending: true,
        actionProposal: null,
        actionConfirmation: null,
        actionExecution: null,
        executionProposalId: null,
        actionError: null,
        actionStatus: "Preparing a confirmation-only preview.",
      });
    },
    receiveActionProposal(result) {
      publish({
        isActionSending: false,
        actionProposal: result,
        actionConfirmation: null,
        actionExecution: null,
        actionError: null,
        actionStatus: "Review the exact preview, then confirm or cancel.",
      });
    },
    beginActionConfirmation(decision) {
      publish({
        isActionSending: true,
        actionError: null,
        actionStatus: decision === "accept" ? "Confirming the reviewed action." : "Cancelling intent.",
      });
    },
    receiveActionConfirmation(result, proposalId) {
      publish({
        isActionSending: false,
        actionProposal: null,
        actionConfirmation: result,
        actionExecution: null,
        executionProposalId: result.execution_ready ? proposalId : null,
        actionError: null,
        actionStatus: result.message,
      });
    },
    beginActionExecution() {
      publish({
        isActionSending: true,
        actionError: null,
        actionStatus: "Revalidating permission and current candidate state before execution.",
      });
    },
    receiveActionExecution(result) {
      publish({
        isActionSending: false,
        actionConfirmation: null,
        actionExecution: result.execution,
        executionProposalId: null,
        actionError: null,
        actionStatus: result.execution.safe_message,
      });
    },
    failAction(error, phase = "preparation") {
      const ambiguous = phase === "execution" && ["timeout", "offline", "adapter_failure"].includes(error.kind);
      publish({
        isActionSending: false,
        actionConfirmation: phase === "execution" ? null : snapshot.actionConfirmation,
        executionProposalId: phase === "execution" ? null : snapshot.executionProposalId,
        actionError: error,
        actionStatus: ambiguous
          ? "OrkaATS did not confirm the outcome. Do not retry; reconcile by idempotency key."
          : error.message,
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
        isActionSending: false,
        actionProposal: null,
        actionConfirmation: null,
        actionExecution: null,
        executionProposalId: null,
        actionError: null,
        actionStatus: "One mock-only start-date action is available after confirmation.",
        error: null,
        status: "Conversation reset.",
      });
    },
  };
}
