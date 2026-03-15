"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type {
  DecisionPointRead,
  DecisionPointUpdate,
} from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export function useDecisions(conversationId: string | null) {
  const {
    data: decisions,
    mutate,
    isLoading,
  } = useSWR<DecisionPointRead[]>(
    conversationId
      ? `/conversations/${conversationId}/decisions`
      : null,
  );

  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detectDecisions = useCallback(() => {
    if (!conversationId || isDetecting) return;

    setIsDetecting(true);
    setError(null);

    streamSSE(
      `/conversations/${conversationId}/decisions/detect`,
      {},
      {
        onEvent: (event, data) => {
          switch (event) {
            case "decision_found": {
              const dp = data as DecisionPointRead;
              mutate((prev) => [...(prev ?? []), dp], { revalidate: false });
              break;
            }
            case "done": {
              setIsDetecting(false);
              mutate();
              break;
            }
            case "error": {
              setError((data as { detail: string }).detail);
              setIsDetecting(false);
              break;
            }
          }
        },
        onError: (err) => {
          setError(err.message);
          setIsDetecting(false);
        },
      },
    );
  }, [conversationId, isDetecting, mutate]);

  const updateDecision = async (
    decisionId: string,
    update: DecisionPointUpdate,
  ) => {
    const updated = await api.patch<DecisionPointRead>(
      `/decisions/${decisionId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deleteDecision = async (decisionId: string) => {
    await api.del(`/decisions/${decisionId}`);
    await mutate();
  };

  return {
    decisions: decisions ?? [],
    isLoading,
    isDetecting,
    error,
    detectDecisions,
    updateDecision,
    deleteDecision,
  };
}
