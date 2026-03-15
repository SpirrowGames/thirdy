"use client";

import { useCallback, useRef } from "react";
import { streamSSE, type SSEHandlers } from "@/lib/sse";

export function useSSE() {
  const controllerRef = useRef<AbortController | null>(null);

  const start = useCallback(
    (path: string, body: unknown, handlers: SSEHandlers) => {
      // Abort any existing stream
      controllerRef.current?.abort();
      const controller = streamSSE(path, body, handlers);
      controllerRef.current = controller;
      return controller;
    },
    [],
  );

  const stop = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  return { start, stop };
}
