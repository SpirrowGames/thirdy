"use client";

import { useCallback, useRef, useState } from "react";
import useSWR from "swr";
import type { MessageRead, SSEMessageSaved, SSEToken } from "@/types/api";
import { streamSSE } from "@/lib/sse";

interface UseChatOptions {
  conversationId: string | null;
  onConversationCreated?: (conversationId: string) => void;
}

export function useChat({ conversationId, onConversationCreated }: UseChatOptions) {
  const {
    data: messages,
    mutate,
    isLoading: isLoadingMessages,
  } = useSWR<MessageRead[]>(
    conversationId ? `/conversations/${conversationId}/messages` : null,
  );

  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || isStreaming) return;

      setError(null);
      setIsStreaming(true);
      setStreamingContent("");

      // Optimistic user message
      const optimisticMessage: MessageRead = {
        id: `temp-${Date.now()}`,
        conversation_id: conversationId ?? "",
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };

      mutate(
        (prev) => [...(prev ?? []), optimisticMessage],
        { revalidate: false },
      );

      let accumulated = "";
      let displayed = "";
      let lineBuffer = "";
      let lastTokenTime = Date.now();

      // Token timeout: if no token received for 30s, treat as error
      if (timeoutRef.current) clearInterval(timeoutRef.current);
      const tokenTimeoutInterval = setInterval(() => {
        if (Date.now() - lastTokenTime > 30000 && accumulated === "") {
          // No tokens at all for 30s — likely LLM not responding
          clearInterval(tokenTimeoutInterval);
          controllerRef.current?.abort();
          setError("応答がタイムアウトしました。LLMサーバーが応答していない可能性があります。");
          setIsStreaming(false);
          setStreamingContent("");
        }
      }, 5000);
      timeoutRef.current = tokenTimeoutInterval;

      controllerRef.current = streamSSE(
        "/chat",
        {
          conversation_id: conversationId,
          content,
        },
        {
          onEvent: (event, data) => {
            switch (event) {
              case "message_saved": {
                const saved = data as SSEMessageSaved;
                if (!conversationId) {
                  onConversationCreated?.(saved.conversation_id);
                }
                break;
              }
              case "token": {
                const token = data as SSEToken;
                accumulated += token.content;
                lineBuffer += token.content;
                lastTokenTime = Date.now();
                // Flush buffer on newline
                if (lineBuffer.includes("\n")) {
                  displayed = accumulated;
                  lineBuffer = "";
                  setStreamingContent(displayed);
                }
                break;
              }
              case "done": {
                clearInterval(tokenTimeoutInterval);
                // Flush remaining buffer so last line is visible
                if (lineBuffer) {
                  setStreamingContent(accumulated);
                }
                // mutate fetches the saved message from DB, then clear streaming
                mutate().then(() => {
                  setIsStreaming(false);
                  setStreamingContent("");
                });
                break;
              }
              case "error": {
                clearInterval(tokenTimeoutInterval);
                const err = data as { detail: string };
                setError(err.detail);
                setIsStreaming(false);
                setStreamingContent("");
                break;
              }
            }
          },
          onError: (err) => {
            clearInterval(tokenTimeoutInterval);
            setError(err.message);
            setIsStreaming(false);
            setStreamingContent("");
          },
          onDone: () => {
            // Stream finished at transport level
          },
        },
      );
    },
    [conversationId, isStreaming, mutate, onConversationCreated],
  );

  const stopStreaming = useCallback(() => {
    if (timeoutRef.current) clearInterval(timeoutRef.current);
    controllerRef.current?.abort();
    setIsStreaming(false);
    setStreamingContent("");
  }, []);

  return {
    messages: messages ?? [],
    streamingContent,
    isStreaming,
    isLoadingMessages,
    error,
    sendMessage,
    stopStreaming,
    mutate,
  };
}
