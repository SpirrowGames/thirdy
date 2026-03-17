"use client";

import { useCosts } from "@/hooks/use-costs";

function formatCost(usd: number): string {
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  return `$${usd.toFixed(2)}`;
}

export function CostWidget() {
  const { costs: today } = useCosts("today");
  const { costs: month } = useCosts("month");

  if (!today && !month) return null;

  return (
    <div className="border-t px-4 py-2 text-xs text-muted-foreground">
      <div className="flex items-center justify-between">
        <span>Today</span>
        <span className="font-mono">
          {today ? formatCost(today.summary.total_cost_usd) : "..."}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span>This month</span>
        <span className="font-mono">
          {month ? formatCost(month.summary.total_cost_usd) : "..."}
        </span>
      </div>
      {today && today.summary.total_requests > 0 && (
        <div className="mt-1 text-[10px] opacity-60">
          {today.summary.total_requests} requests |{" "}
          {(today.summary.total_tokens_input + today.summary.total_tokens_output).toLocaleString()} tokens
        </div>
      )}
    </div>
  );
}
