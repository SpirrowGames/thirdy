"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type { GeneratedCodeRead, GeneratedCodeUpdate, SSEToken } from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export function useCodes(conversationId: string | null) {
  const {
    data: codes,
    mutate,
    isLoading,
  } = useSWR<GeneratedCodeRead[]>(
    conversationId
      ? `/conversations/${conversationId}/codes`
      : null,
  );

  const [isGenerating, setIsGenerating] = useState(false);
  const [generatingContent, setGeneratingContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const generateCode = useCallback(
    (taskId: string) => {
      if (!conversationId || isGenerating) return;

      setIsGenerating(true);
      setGeneratingContent("");
      setError(null);

      let accumulated = "";

      streamSSE(
        `/conversations/${conversationId}/codes/generate`,
        { task_id: taskId },
        {
          onEvent: (event, data) => {
            switch (event) {
              case "token": {
                accumulated += (data as SSEToken).content;
                setGeneratingContent(accumulated);
                break;
              }
              case "done": {
                setIsGenerating(false);
                setGeneratingContent("");
                mutate();
                break;
              }
              case "error": {
                setError((data as { detail: string }).detail);
                setIsGenerating(false);
                setGeneratingContent("");
                break;
              }
            }
          },
          onError: (err) => {
            setError(err.message);
            setIsGenerating(false);
          },
        },
      );
    },
    [conversationId, isGenerating, mutate],
  );

  const updateCode = async (codeId: string, update: GeneratedCodeUpdate) => {
    const updated = await api.patch<GeneratedCodeRead>(
      `/codes/${codeId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deleteCode = async (codeId: string) => {
    await api.del(`/codes/${codeId}`);
    await mutate();
  };

  return {
    codes: codes ?? [],
    isLoading,
    isGenerating,
    generatingContent,
    error,
    generateCode,
    updateCode,
    deleteCode,
  };
}
