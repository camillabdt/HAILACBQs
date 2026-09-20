const DEFAULT_TIMEOUT = 12_000;

export class HailaApiError extends Error {
  constructor(message, status = 0, payload = null) {
    super(message);
    this.name = "HailaApiError";
    this.status = status;
    this.payload = payload;
  }
}

export class HailaApi {
  constructor(baseUrl = "/api") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async request(path, options = {}) {
    const timeout = options.timeout ?? DEFAULT_TIMEOUT;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(this.baseUrl + path, {
        method: options.method ?? "GET",
        headers: { "Content-Type": "application/json" },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal ?? controller.signal,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = payload?.detail;
        throw new HailaApiError(
          typeof detail === "string" ? detail : "O motor não conseguiu concluir a solicitação.",
          response.status,
          payload,
        );
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new HailaApiError("O motor demorou mais que o esperado para responder.");
      }
      if (error instanceof HailaApiError) throw error;
      throw new HailaApiError("Não foi possível acessar o motor HAILA.");
    } finally {
      clearTimeout(timer);
    }
  }

  health() {
    return this.request("/health");
  }

  createRequest(specification) {
    return this.request("/requests", { method: "POST", body: specification });
  }

  generate(requestId) {
    return this.request(`/requests/${encodeURIComponent(requestId)}/generate`, {
      method: "POST",
      body: {},
      timeout: 30 * 60 * 1000,
    });
  }

  history(requestId) {
    return this.request(`/requests/${encodeURIComponent(requestId)}`);
  }
}
