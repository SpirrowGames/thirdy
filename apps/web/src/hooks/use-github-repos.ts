"use client";

import useSWR from "swr";
import type { RepoInfo, CreateRepoRequest } from "@/types/api";
import { api } from "@/lib/api-client";

interface GitHubConfigStatus {
  configured: boolean;
  org: string | null;
}

export function useGitHubConfig() {
  const { data, isLoading } = useSWR<GitHubConfigStatus>("/github/config");
  return {
    configured: data?.configured ?? false,
    org: data?.org ?? null,
    isLoading,
  };
}

export function useGitHubRepos() {
  const config = useGitHubConfig();

  const { data, error, isLoading, mutate } = useSWR<RepoInfo[]>(
    config.configured ? "/github/repos" : null,
  );

  const createRepo = async (body: CreateRepoRequest): Promise<RepoInfo> => {
    const repo = await api.post<RepoInfo>("/github/repos", body);
    await mutate();
    return repo;
  };

  return {
    repos: data ?? [],
    error,
    isLoading,
    mutate,
    createRepo,
    config,
  };
}
