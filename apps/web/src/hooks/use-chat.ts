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
                setStreamingContent(accumulated);
                break;
              }
              case "done": {
                setIsStreaming(false);
                setStreamingContent("");
                mutate();
                break;
              }
              case "error": {
                const err = data as { detail: string };
                setError(err.detail);
                setIsStreaming(false);
                setStreamingContent("");
                break;
              }
            }
          },
          onError: (err) => {
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
