"use client";

import { useCallback, useState } from "react";
import type {
  MeetingSuggestion as MeetingSuggestionType,
  VoteSessionRead,
  DecisionOptionRead,
} from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { VoteTally } from "./vote-tally";
import { MeetingSuggestion } from "./meeting-suggestion";

const STATUS_COLORS: Record<string, string> = {
  open: "bg-blue-500/10 text-blue-600",
  closed: "bg-green-500/10 text-green-600",
  split: "bg-orange-500/10 text-orange-600",
};

interface VoteSessionCardProps {
  session: VoteSessionRead;
  options: DecisionOptionRead[];
  onClose: (sessionId: string) => Promise<unknown>;
  onGetMeetingSuggestion: (sessionId: string) => Promise<MeetingSuggestionType>;
}

export function VoteSessionCard({
  session,
  options,
  onClose,
  onGetMeetingSuggestion,
}: VoteSessionCardProps) {
  const [isClosing, setIsClosing] = useState(false);
  const [meetingSuggestion, setMeetingSuggestion] =
    useState<MeetingSuggestionType | null>(null);
  const [copied, setCopied] = useState(false);

  const shareUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/vote/${session.share_token}`;

  const copyShareLink = useCallback(async () => {
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [shareUrl]);

  const handleClose = async () => {
    setIsClosing(true);
    try {
      await onClose(session.id);
    } finally {
      setIsClosing(false);
    }
  };

  const handleGetMeeting = async () => {
    const suggestion = await onGetMeetingSuggestion(session.id);
    setMeetingSuggestion(suggestion);
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Vote Session</CardTitle>
          <Badge
            variant="secondary"
            className={STATUS_COLORS[session.status] ?? ""}
          >
            {session.status}
          </Badge>
        </div>
        {session.deadline && (
          <p className="text-xs text-muted-foreground">
            Deadline: {new Date(session.deadline).toLocaleString()}
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        <VoteTally tally={session.tally} totalVotes={session.total_votes} />

        <div className="flex gap-2 flex-wrap">
          <Button size="sm" variant="outline" onClick={copyShareLink}>
            {copied ? "Copied!" : "Copy Share Link"}
          </Button>

          {session.status === "open" && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleClose}
              disabled={isClosing}
            >
              {isClosing ? "Closing..." : "Close Voting"}
            </Button>
          )}

          {session.status === "split" && !meetingSuggestion && (
            <Button size="sm" variant="outline" onClick={handleGetMeeting}>
              Suggest Meeting
            </Button>
          )}
        </div>

        {meetingSuggestion && (
          <MeetingSuggestion suggestion={meetingSuggestion} sessionId={session.id} />
        )}
      </CardContent>
    </Card>
  );
}
