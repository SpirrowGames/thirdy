import { getToken, clearToken } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SSEHandlers {
  onEvent?: (event: string, data: unknown) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

export function streamSSE(
  path: string,
  body: unknown,
  handlers: SSEHandlers,
): AbortController {
  const controller = new AbortController();

  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  (async () => {
    try {
      const res = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (res.status === 401) {
        clearToken();
        window.location.href = "/login";
        return;
      }

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        handlers.onError?.(new Error(errBody.detail ?? res.statusText));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        handlers.onError?.(new Error("No response body"));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent) {
                handlers.onEvent?.(currentEvent, data);
              }
            } catch {
              // skip malformed JSON
            }
            currentEvent = "";
          }
        }
      }

      handlers.onDone?.();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.(err as Error);
      }
    }
  })();

  return controller;
}

export function streamSSEUpload(
  path: string,
  formData: FormData,
  handlers: SSEHandlers,
): AbortController {
  const controller = new AbortController();

  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  // Do NOT set Content-Type — browser auto-sets multipart boundary

  (async () => {
    try {
      const res = await fetch(`${API_URL}${path}`, {
        method: "POST",
        headers,
        body: formData,
        signal: controller.signal,
      });

      if (res.status === 401) {
        clearToken();
        window.location.href = "/login";
        return;
      }

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({ detail: res.statusText }));
        handlers.onError?.(new Error(errBody.detail ?? res.statusText));
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        handlers.onError?.(new Error("No response body"));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              if (currentEvent) {
                handlers.onEvent?.(currentEvent, data);
              }
            } catch {
              // skip malformed JSON
            }
            currentEvent = "";
          }
        }
      }

      handlers.onDone?.();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.(err as Error);
      }
    }
  })();

  return controller;
}
