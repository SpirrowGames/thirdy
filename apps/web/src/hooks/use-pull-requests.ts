"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type { PullRequestRead, PullRequestUpdate } from "@/types/api";
import { api } from "@/lib/api-client";
import { streamSSE } from "@/lib/sse";

export interface PRProgress {
  step: string;
  detail?: string;
}

export function usePullRequests(conversationId: string | null) {
  const {
    data: pullRequests,
    mutate,
    isLoading,
  } = useSWR<PullRequestRead[]>(
    conversationId
      ? `/conversations/${conversationId}/pull-requests`
      : null,
  );

  const [isCreating, setIsCreating] = useState(false);
  const [progress, setProgress] = useState<PRProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createPR = useCallback(
    (codeId: string) => {
      if (!conversationId || isCreating) return;

      setIsCreating(true);
      setProgress({ step: "Starting..." });
      setError(null);

      streamSSE(
        `/conversations/${conversationId}/pull-requests/create`,
        { code_id: codeId },
        {
          onEvent: (event, data) => {
            switch (event) {
              case "pr_started": {
                setProgress({ step: "Initializing PR creation..." });
                break;
              }
              case "branch_created": {
                const d = data as { branch_name: string };
                setProgress({
                  step: "Branch created",
                  detail: d.branch_name,
                });
                break;
              }
              case "files_committed": {
                const d = data as { file_count: number; files: string[] };
                setProgress({
                  step: "Files committed",
                  detail: `${d.file_count} file(s)`,
                });
                break;
              }
              case "pr_created": {
                const d = data as { pr_number: number; pr_url: string };
                setProgress({
                  step: "Pull request created",
                  detail: `#${d.pr_number}`,
                });
                break;
              }
              case "done": {
                setIsCreating(false);
                setProgress(null);
                mutate();
                break;
              }
              case "error": {
                setError((data as { detail: string }).detail);
                setIsCreating(false);
                setProgress(null);
                break;
              }
            }
          },
          onError: (err) => {
            setError(err.message);
            setIsCreating(false);
            setProgress(null);
          },
        },
      );
    },
    [conversationId, isCreating, mutate],
  );

  const updatePR = async (prId: string, update: PullRequestUpdate) => {
    const updated = await api.patch<PullRequestRead>(
      `/pull-requests/${prId}`,
      update,
    );
    await mutate();
    return updated;
  };

  const deletePR = async (prId: string) => {
    await api.del(`/pull-requests/${prId}`);
    await mutate();
  };

  return {
    pullRequests: pullRequests ?? [],
    isLoading,
    isCreating,
    progress,
    error,
    createPR,
    updatePR,
    deletePR,
  };
}
