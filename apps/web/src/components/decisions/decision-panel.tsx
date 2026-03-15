"use client";

import { useDecisions } from "@/hooks/use-decisions";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { DecisionCard } from "./decision-card";

interface DecisionPanelProps {
  conversationId: string | null;
}

export function DecisionPanel({ conversationId }: DecisionPanelProps) {
  const {
    decisions,
    isLoading,
    isDetecting,
    error,
    detectDecisions,
    updateDecision,
    deleteDecision,
  } = useDecisions(conversationId);

  // Show pending first
  const sorted = [...decisions].sort((a, b) => {
    if (a.status === "pending" && b.status !== "pending") return -1;
    if (a.status !== "pending" && b.status === "pending") return 1;
    return 0;
  });

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-3">
        <Button
          onClick={detectDecisions}
          disabled={!conversationId || isDetecting}
          size="sm"
          className="w-full"
        >
          {isDetecting ? "Detecting..." : "Detect Decisions"}
        </Button>
      </div>

      {error && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {decisions.length > 0 && (
        <div className="border-b px-3 py-2 text-xs text-muted-foreground">
          {decisions.filter((d) => d.status === "pending").length} pending
          {" · "}
          {decisions.filter((d) => d.status === "resolved").length} resolved
          {" · "}
          {decisions.filter((d) => d.status === "dismissed").length} dismissed
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : sorted.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No decisions detected yet. Click &quot;Detect Decisions&quot; to
            analyze the conversation.
          </p>
        ) : (
          <div className="space-y-3">
            {sorted.map((dp) => (
              <DecisionCard
                key={dp.id}
                decision={dp}
                onResolve={(id, optionId, note) =>
                  updateDecision(id, {
                    status: "resolved",
                    resolved_option_id: optionId,
                    resolution_note: note || undefined,
                  })
                }
                onDismiss={(id, note) =>
                  updateDecision(id, {
                    status: "dismissed",
                    resolution_note: note || undefined,
                  })
                }
                onDelete={deleteDecision}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
