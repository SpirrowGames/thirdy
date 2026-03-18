import { getToken, clearToken } from "./auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SSEHandlers {
  onEvent?: (event: string, data: unknown) => void;
  onError?: (error: Error) => void;
  onDone?: () => void;
}

/**
 * Parse SSE event blocks from a buffer.
 * SSE events are separated by double newlines (\n\n).
 * Each block may have "event:" and "data:" lines.
 * Data lines can span multiple lines (rejoined for JSON parsing).
 */
function parseSSEBuffer(
  buffer: string,
  handler: (event: string, data: unknown) => void,
): string {
  const blocks = buffer.split("\n\n");
  const remaining = blocks.pop() ?? "";

  for (const block of blocks) {
    if (!block.trim()) continue;
    const lines = block.split("\n");
    let eventName = "";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventName = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        dataLines.push(line.slice(6));
      }
    }
    if (eventName && dataLines.length > 0) {
      const dataStr = dataLines.join("\n");
      try {
        const data = JSON.parse(dataStr);
        handler(eventName, data);
      } catch {
        // skip malformed JSON
      }
    }
  }

  return remaining;
}

async function processSSEResponse(
  res: Response,
  handlers: SSEHandlers,
): Promise<void> {
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
    buffer = parseSSEBuffer(buffer, (event, data) => {
      handlers.onEvent?.(event, data);
    });
  }

  // Process any remaining buffer
  if (buffer.trim()) {
    parseSSEBuffer(buffer + "\n\n", (event, data) => {
      handlers.onEvent?.(event, data);
    });
  }

  handlers.onDone?.();
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

      await processSSEResponse(res, handlers);
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

      await processSSEResponse(res, handlers);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        handlers.onError?.(err as Error);
      }
    }
  })();

  return controller;
}
