"use client";

import { useParams } from "next/navigation";
import { usePublicVote } from "@/hooks/use-votes";
import { VoteForm } from "@/components/votes/vote-form";
import { VoteTally } from "@/components/votes/vote-tally";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function PublicVotePage() {
  const params = useParams();
  const shareToken = params.shareToken as string;

  const {
    session,
    decision,
    tally,
    totalVotes,
    castVote,
    isLoading,
    isVoting,
    error,
  } = usePublicVote(shareToken);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-muted-foreground">Loading vote session...</p>
      </div>
    );
  }

  if (error || !session || !decision) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-destructive">{error ?? "Session not found"}</p>
      </div>
    );
  }

  const isClosed = session.session.status !== "open";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg">{decision.question}</CardTitle>
            <Badge
              variant="secondary"
              className={
                isClosed
                  ? "bg-gray-500/10 text-gray-500"
                  : "bg-blue-500/10 text-blue-600"
              }
            >
              {session.session.status}
            </Badge>
          </div>
          {decision.context && (
            <p className="mt-2 text-sm text-muted-foreground">
              {decision.context}
            </p>
          )}
          {decision.recommendation && (
            <p className="mt-1 text-xs text-muted-foreground">
              Recommendation: {decision.recommendation}
            </p>
          )}
        </CardHeader>
      </Card>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Cast Your Vote</CardTitle>
          </CardHeader>
          <CardContent>
            {isClosed ? (
              <p className="text-sm text-muted-foreground">
                Voting has been closed.
              </p>
            ) : (
              <VoteForm
                options={decision.options}
                onVote={castVote}
                isVoting={isVoting}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Results</CardTitle>
          </CardHeader>
          <CardContent>
            <VoteTally tally={tally} totalVotes={totalVotes} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
