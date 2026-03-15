"use client";

import { useCallback, useState } from "react";
import useSWR, { useSWRConfig } from "swr";
import type { DesignRead, DesignUpdate, SSEToken } from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export function useDesigns(conversationId: string | null) {
  const { mutate: globalMutate } = useSWRConfig();
  const {
    data: designs,
    mutate,
    isLoading,
  } = useSWR<DesignRead[]>(
    conversationId
      ? `/conversations/${conversationId}/designs`
      : null,
  );

  const [isDecomposing, setIsDecomposing] = useState(false);
  const [decompositionContent, setDecompositionContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  const decomposeDesign = useCallback(
    (specId: string) => {
      if (!conversationId || isDecomposing) return;

      setIsDecomposing(true);
      setDecompositionContent("");
      setError(null);

      let accumulated = "";

      streamSSE(
        `/conversations/${conversationId}/designs/decompose`,
        { spec_id: specId },
        {
          onEvent: (event, data) => {
            switch (event) {
              case "token": {
                accumulated += (data as SSEToken).content;
                setDecompositionContent(accumulated);
                break;
              }
              case "design_saved": {
                // Design saved, decision detection phase starting
                break;
              }
              case "decision_found": {
                // Decision points will be picked up by useDecisions mutate
                break;
              }
              case "done": {
                setIsDecomposing(false);
                setDecompositionContent("");
                mutate();
                // Invalidate decisions SWR cache so Decisions tab picks up new decision_points
                globalMutate(
                  (key: unknown) => typeof key === "string" && key.includes("/decisions"),
                  undefined,
                  { revalidate: true },
                );
                break;
              }
              case "error": {
                setError((data as { detail: string }).detail);
                setIsDecomposing(false);
                setDecompositionContent("");
                break;
              }
            }
          },
          onError: (err) => {
            setError(err.message);
            setIsDecomposing(false);
          },
        },
      );
    },
    [conversationId, isDecomposing, mutate, globalMutate],
  );

  const updateDesign = async (designId: string, update: DesignUpdate) => {
    const updated = await api.patch<DesignRead>(
      `/designs/${designId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deleteDesign = async (designId: string) => {
    await api.del(`/designs/${designId}`);
    await mutate();
  };

  return {
    designs: designs ?? [],
    isLoading,
    isDecomposing,
    decompositionContent,
    error,
    decomposeDesign,
    updateDesign,
    deleteDesign,
  };
}
