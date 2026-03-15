"use client";

import { useState } from "react";
import type { DecisionPointRead, DecisionStatus } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { OptionSelector } from "./option-selector";
import { useVoteSessions } from "@/hooks/use-votes";
import { VoteSessionCard } from "@/components/votes/vote-session-card";

const STATUS_COLORS: Record<DecisionStatus, string> = {
  pending: "bg-orange-500/10 text-orange-600",
  resolved: "bg-green-500/10 text-green-600",
  dismissed: "bg-gray-500/10 text-gray-500",
};

interface DecisionCardProps {
  decision: DecisionPointRead;
  onResolve: (
    decisionId: string,
    optionId: string,
    note: string,
  ) => void;
  onDismiss: (decisionId: string, note: string) => void;
  onDelete: (decisionId: string) => void;
}

export function DecisionCard({
  decision,
  onResolve,
  onDismiss,
  onDelete,
}: DecisionCardProps) {
  const [expanded, setExpanded] = useState(decision.status === "pending");
  const isPending = decision.status === "pending";

  const {
    sessions,
    createSession,
    closeSession,
    getMeetingSuggestion,
    mutate,
  } = useVoteSessions(decision.id);

  const [isCreatingVote, setIsCreatingVote] = useState(false);

  const handleStartVote = async () => {
    setIsCreatingVote(true);
    try {
      await createSession();
    } finally {
      setIsCreatingVote(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">
            {decision.question}
          </CardTitle>
          <Badge variant="secondary" className={STATUS_COLORS[decision.status]}>
            {decision.status}
          </Badge>
        </div>
        {decision.recommendation && (
          <p className="mt-1 text-xs text-muted-foreground">
            Recommendation: {decision.recommendation}
          </p>
        )}
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-xs text-muted-foreground line-clamp-2">
          {decision.context}
        </p>

        {isPending && (
          <div className="flex gap-2 mb-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Hide options" : "Show options"}
            </Button>
            {sessions.length === 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 text-xs"
                onClick={handleStartVote}
                disabled={isCreatingVote}
              >
                {isCreatingVote ? "Creating..." : "Start Vote"}
              </Button>
            )}
          </div>
        )}

        {expanded && isPending && (
          <OptionSelector
            options={decision.options}
            onResolve={(optionId, note) =>
              onResolve(decision.id, optionId, note)
            }
            onDismiss={(note) => onDismiss(decision.id, note)}
          />
        )}

        {sessions.length > 0 && (
          <div className="mt-3 space-y-2">
            {sessions.map((s) => (
              <VoteSessionCard
                key={s.id}
                session={s}
                options={decision.options}
                onClose={closeSession}
                onGetMeetingSuggestion={getMeetingSuggestion}
                onMutate={mutate}
              />
            ))}
          </div>
        )}

        {decision.status === "resolved" && decision.resolution_note && (
          <p className="text-xs text-muted-foreground italic">
            Note: {decision.resolution_note}
          </p>
        )}

        {!isPending && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 h-6 text-xs text-destructive"
            onClick={() => onDelete(decision.id)}
          >
            Delete
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
