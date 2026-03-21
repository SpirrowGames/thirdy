"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";
import type {
  SpecReviewRead,
  SpecReviewTriggerResponse,
  SuggestionApplyResponse,
} from "@/types/spec-review";

export function useSpecReviews(
  conversationId: string | null,
  specId: string | null,
) {
  const {
    data: reviews,
    error,
    mutate,
  } = useSWR<SpecReviewRead[]>(
    conversationId && specId
      ? `/conversations/${conversationId}/specs/${specId}/reviews`
      : null,
    { refreshInterval: 10000 },
  );

  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const triggerReview = useCallback(
    async (scope: "full" | "quick" = "full") => {
      if (!conversationId || !specId) return;
      setIsTriggering(true);
      setTriggerError(null);
      try {
        await api.post<SpecReviewTriggerResponse>(
          `/conversations/${conversationId}/specs/${specId}/review`,
          { scope },
        );
        await mutate();
      } catch (err) {
        setTriggerError(
          err instanceof Error ? err.message : "Failed to trigger review",
        );
      } finally {
        setIsTriggering(false);
      }
    },
    [conversationId, specId, mutate],
  );

  const applySuggestion = useCallback(
    async (
      reviewId: string,
      suggestionIdx: number,
      confirm: boolean,
    ): Promise<SuggestionApplyResponse | null> => {
      if (!conversationId || !specId) return null;
      try {
        const res = await api.patch<SuggestionApplyResponse>(
          `/conversations/${conversationId}/specs/${specId}/reviews/${reviewId}/suggestions/${suggestionIdx}/apply`,
          { confirm },
        );
        if (confirm) await mutate();
        return res;
      } catch (err) {
        setTriggerError(
          err instanceof Error ? err.message : "Failed to apply suggestion",
        );
        return null;
      }
    },
    [conversationId, specId, mutate],
  );

  const dismissSuggestion = useCallback(
    async (reviewId: string, suggestionIdx: number) => {
      if (!conversationId || !specId) return;
      try {
        await api.patch(
          `/conversations/${conversationId}/specs/${specId}/reviews/${reviewId}/suggestions/${suggestionIdx}/dismiss`,
          {},
        );
        await mutate();
      } catch (err) {
        setTriggerError(
          err instanceof Error ? err.message : "Failed to dismiss suggestion",
        );
      }
    },
    [conversationId, specId, mutate],
  );

  const deleteReview = useCallback(
    async (reviewId: string) => {
      if (!conversationId || !specId) return;
      await api.del(
        `/conversations/${conversationId}/specs/${specId}/reviews/${reviewId}`,
      );
      await mutate();
    },
    [conversationId, specId, mutate],
  );

  return {
    reviews: reviews ?? [],
    isLoading: !reviews && !error,
    error,
    isTriggering,
    triggerError,
    triggerReview,
    applySuggestion,
    dismissSuggestion,
    deleteReview,
    mutate,
  };
}
