"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type { SpecRead, SpecUpdate, SSEToken } from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export function useSpecs(conversationId: string | null) {
  const {
    data: specs,
    mutate,
    isLoading,
  } = useSWR<SpecRead[]>(
    conversationId
      ? `/conversations/${conversationId}/specifications`
      : null,
    { refreshInterval: 10000 },
  );

  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionContent, setExtractionContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const extractSpec = useCallback(() => {
    if (!conversationId || isExtracting) return;

    setIsExtracting(true);
    setExtractionContent("");
    setError(null);

    let accumulated = "";

    streamSSE(
      `/conversations/${conversationId}/specifications/extract`,
      {},
      {
        onEvent: (event, data) => {
          switch (event) {
            case "token": {
              accumulated += (data as SSEToken).content;
              setExtractionContent(accumulated);
              break;
            }
            case "done": {
              setIsExtracting(false);
              setExtractionContent("");
              mutate();
              break;
            }
            case "error": {
              setError((data as { detail: string }).detail);
              setIsExtracting(false);
              setExtractionContent("");
              break;
            }
          }
        },
        onError: (err) => {
          setError(err.message);
          setIsExtracting(false);
        },
      },
    );
  }, [conversationId, isExtracting, mutate]);

  const updateSpec = async (specId: string, update: SpecUpdate) => {
    const updated = await api.patch<SpecRead>(
      `/specifications/${specId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deleteSpec = async (specId: string) => {
    await api.del(`/specifications/${specId}`);
    await mutate();
  };

  return {
    specs: specs ?? [],
    isLoading,
    isExtracting,
    extractionContent,
    error,
    extractSpec,
    updateSpec,
    deleteSpec,
  };
}
