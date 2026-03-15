"use client";

import type { VoteTally as VoteTallyType } from "@/types/api";

interface VoteTallyProps {
  tally: VoteTallyType[];
  totalVotes: number;
}

export function VoteTally({ tally, totalVotes }: VoteTallyProps) {
  if (tally.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No votes yet.</p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {totalVotes} vote{totalVotes !== 1 ? "s" : ""} cast
      </p>
      {tally.map((item) => (
        <div key={item.option_id} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">{item.option_label}</span>
            <span className="text-muted-foreground">
              {item.count} ({item.percentage}%)
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300"
              style={{ width: `${item.percentage}%` }}
            />
          </div>
          {item.voters.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {item.voters.join(", ")}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
