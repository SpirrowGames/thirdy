"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";
import type { WatchReportRead, WatchTriggerResponse } from "@/types/watch";

export function useWatches(conversationId: string | null) {
  const {
    data: reports,
    error,
    mutate,
  } = useSWR<WatchReportRead[]>(
    conversationId
      ? `/conversations/${conversationId}/watches`
      : null,
    { refreshInterval: 30000 },
  );

  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const triggerWatch = useCallback(async () => {
    if (!conversationId) return;
    setIsTriggering(true);
    setTriggerError(null);
    try {
      await api.post<WatchTriggerResponse>(
        `/conversations/${conversationId}/watch`,
        {},
      );
      await mutate();
    } catch (err) {
      setTriggerError(
        err instanceof Error ? err.message : "Failed to trigger watch",
      );
    } finally {
      setIsTriggering(false);
    }
  }, [conversationId, mutate]);

  const deleteWatch = useCallback(
    async (watchId: string) => {
      await api.del(`/watches/${watchId}`);
      await mutate();
    },
    [mutate],
  );

  return {
    reports: reports ?? [],
    isLoading: !reports && !error,
    error,
    isTriggering,
    triggerError,
    triggerWatch,
    deleteWatch,
  };
}
