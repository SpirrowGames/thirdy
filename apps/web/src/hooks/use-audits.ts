"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";
import type { AuditReportRead, AuditTriggerResponse } from "@/types/audit";

export function useAudits(conversationId: string | null) {
  const {
    data: reports,
    error,
    mutate,
  } = useSWR<AuditReportRead[]>(
    conversationId
      ? `/conversations/${conversationId}/audits`
      : null,
    { refreshInterval: 30000 },
  );

  const [isTriggering, setIsTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const triggerAudit = useCallback(async () => {
    if (!conversationId) return;
    setIsTriggering(true);
    setTriggerError(null);
    try {
      await api.post<AuditTriggerResponse>(
        `/conversations/${conversationId}/audit`,
        {},
      );
      await mutate();
    } catch (err) {
      setTriggerError(
        err instanceof Error ? err.message : "Failed to trigger audit",
      );
    } finally {
      setIsTriggering(false);
    }
  }, [conversationId, mutate]);

  const deleteAudit = useCallback(
    async (auditId: string) => {
      await api.del(`/audits/${auditId}`);
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
    triggerAudit,
    deleteAudit,
  };
}
