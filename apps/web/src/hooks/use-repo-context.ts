"use client";

import useSWR from "swr";
import type { RepoContextResponse } from "@/types/api";

export function useRepoContext(githubRepo: string | null) {
  const parts = githubRepo?.split("/");
  const owner = parts?.[0];
  const repo = parts?.[1];

  const { data, error, isLoading, mutate } = useSWR<RepoContextResponse>(
    owner && repo ? `/github/repos/${owner}/${repo}/context` : null,
  );

  return {
    context: data ?? null,
    error,
    isLoading,
    refresh: mutate,
  };
}
