"use client";

import useSWR from "swr";

interface ArtifactCount {
  total: number;
  draft: number;
  approved: number;
}

interface TaskCount {
  total: number;
  pending: number;
  in_progress: number;
  done: number;
}

interface PRCount {
  total: number;
  created: number;
  merged: number;
  failed: number;
}

interface RepoGroup {
  github_repo: string | null;
  conversation_count: number;
  spec_count: number;
  task_count: number;
  pr_count: number;
}

export interface DashboardSummary {
  conversation_count: number;
  specs: ArtifactCount;
  designs: ArtifactCount;
  tasks: TaskCount;
  codes: ArtifactCount;
  prs: PRCount;
  repos: RepoGroup[];
}

export interface DashboardTask {
  id: string;
  conversation_id: string;
  conversation_title: string | null;
  github_repo: string | null;
  title: string;
  description: string;
  priority: string;
  status: string;
  created_at: string;
}

export interface DashboardPR {
  id: string;
  conversation_id: string;
  conversation_title: string | null;
  github_repo: string | null;
  title: string;
  pr_number: number | null;
  pr_url: string | null;
  status: string;
  created_at: string;
}

export function useDashboardSummary() {
  const { data, error, isLoading } = useSWR<DashboardSummary>(
    "/dashboard/summary",
    { refreshInterval: 30000 },
  );
  return { summary: data ?? null, error, isLoading };
}

export function useDashboardTasks(status?: string) {
  const params = status ? `?status=${status}` : "";
  const { data, error, isLoading } = useSWR<DashboardTask[]>(
    `/dashboard/tasks${params}`,
    { refreshInterval: 30000 },
  );
  return { tasks: data ?? [], error, isLoading };
}

export function useDashboardPRs() {
  const { data, error, isLoading } = useSWR<DashboardPR[]>(
    "/dashboard/prs",
    { refreshInterval: 30000 },
  );
  return { prs: data ?? [], error, isLoading };
}
