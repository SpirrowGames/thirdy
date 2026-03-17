"use client";

import useSWR from "swr";

export interface CostSummary {
  total_requests: number;
  total_tokens_input: number;
  total_tokens_output: number;
  total_cost_usd: number;
  successful_requests: number;
}

export interface CostByModel {
  model: string;
  requests: number;
  tokens_input: number;
  tokens_output: number;
  cost_usd: number;
}

export interface CostDaily {
  date: string;
  requests: number;
  cost_usd: number;
}

export interface CostData {
  period: string;
  filters: { model: string | null; user_id: string | null; backend: string | null };
  summary: CostSummary;
  by_model: CostByModel[];
  daily: CostDaily[];
  pricing: Record<string, { input: number; output: number }>;
}

export function useCosts(period: string = "today") {
  const { data, error, mutate } = useSWR<CostData>(
    `/costs?period=${period}`,
    { refreshInterval: 30000 },
  );

  return {
    costs: data ?? null,
    isLoading: !data && !error,
    error,
    refresh: mutate,
  };
}
