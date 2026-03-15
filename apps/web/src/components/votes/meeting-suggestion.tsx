"use client";

import { useCallback } from "react";
import type { MeetingSuggestion as MeetingSuggestionType } from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface MeetingSuggestionProps {
  suggestion: MeetingSuggestionType;
}

export function MeetingSuggestion({ suggestion }: MeetingSuggestionProps) {
  const downloadICS = useCallback(() => {
    const blob = new Blob([suggestion.ics_content], {
      type: "text/calendar;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "vote-meeting.ics";
    a.click();
    URL.revokeObjectURL(url);
  }, [suggestion.ics_content]);

  const mailtoLink = `mailto:?subject=${encodeURIComponent(suggestion.subject)}&body=${encodeURIComponent(suggestion.description)}`;

  return (
    <Card className="border-orange-500/30 bg-orange-500/5">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-orange-600">
          Vote Split — Meeting Suggested
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground whitespace-pre-line">
          {suggestion.description}
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={downloadICS}>
            Download .ics
          </Button>
          <a
            href={mailtoLink}
            className="inline-flex h-8 items-center justify-center rounded-md border border-input bg-background px-3 text-xs font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Send Email Invite
          </a>
        </div>
      </CardContent>
    </Card>
  );
}
