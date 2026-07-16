export class AssistantTransportError extends Error {
  constructor(kind, message, requestId = null) {
    super(message);
    this.kind = kind;
    this.requestId = requestId;
  }
}

export function createAssistantTransport({ baseUrl = "", fetchFn = fetch, timeoutMs = 5000 } = {}) {
  return {
    async query({ question, context, conversationId }) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      const body = { question, context };
      if (conversationId) body.conversation_id = conversationId;
      try {
        const response = await fetchFn(`${baseUrl}/api/v1/assistant/queries`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        const requestId = response.headers.get("X-Request-ID");
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          const message = payload?.message || "The assistant request could not be completed.";
          const kind = payload?.code?.includes("timeout")
            ? "timeout"
            : response.status === 503
              ? "adapter_failure"
              : "api_error";
          throw new AssistantTransportError(kind, message, requestId);
        }
        return payload;
      } catch (error) {
        if (error instanceof AssistantTransportError) throw error;
        if (error?.name === "AbortError") {
          throw new AssistantTransportError("timeout", "The request timed out. Please try again.");
        }
        throw new AssistantTransportError(
          "offline",
          "The assistant is offline. Check the local service and try again.",
        );
      } finally {
        clearTimeout(timeout);
      }
    },
  };
}
