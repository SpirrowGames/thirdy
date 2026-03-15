"use client";

import { useCallback, useState } from "react";
import type {
  MeetingSuggestion as MeetingSuggestionType,
  CalendarEventPreset,
  CalendarEventResponse,
} from "@/types/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useGoogleCalendar } from "@/hooks/use-google-calendar";

const PRESETS: { value: CalendarEventPreset; label: string; minutes: number }[] = [
  { value: "quick_sync", label: "Quick Sync", minutes: 15 },
  { value: "discussion", label: "Discussion", minutes: 30 },
  { value: "deep_dive", label: "Deep Dive", minutes: 60 },
];

interface MeetingSuggestionProps {
  suggestion: MeetingSuggestionType;
  sessionId: string;
}

export function MeetingSuggestion({ suggestion, sessionId }: MeetingSuggestionProps) {
  const { connected, isLoading: calLoading, isCreating, connect, disconnect, createEvent } =
    useGoogleCalendar();

  const [showForm, setShowForm] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<CalendarEventPreset>("discussion");
  const [attendees, setAttendees] = useState("");
  const [createdEvent, setCreatedEvent] = useState<CalendarEventResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const handleCreate = async () => {
    setError(null);
    try {
      const emails = attendees
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean);
      const event = await createEvent(sessionId, selectedPreset, emails);
      setCreatedEvent(event);
      setShowForm(false);
    } catch (err) {
      setError((err as Error).message);
    }
  };

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

        {/* ICS + mailto (always available) */}
        <div className="flex gap-2 flex-wrap">
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

        {/* Google Calendar integration */}
        {!calLoading && (
          <div className="border-t pt-3 space-y-2">
            {!connected ? (
              <Button size="sm" variant="outline" onClick={connect}>
                Connect Google Calendar
              </Button>
            ) : createdEvent ? (
              <div className="space-y-1">
                <p className="text-xs text-green-600 font-medium">
                  Calendar event created!
                </p>
                <a
                  href={createdEvent.html_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 underline"
                >
                  Open in Google Calendar
                </a>
              </div>
            ) : !showForm ? (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
                  Create Calendar Event
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs text-muted-foreground"
                  onClick={disconnect}
                >
                  Disconnect
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex gap-1">
                  {PRESETS.map((p) => (
                    <Button
                      key={p.value}
                      size="sm"
                      variant={selectedPreset === p.value ? "default" : "outline"}
                      onClick={() => setSelectedPreset(p.value)}
                      className="text-xs"
                    >
                      {p.label} ({p.minutes}m)
                    </Button>
                  ))}
                </div>
                <Input
                  placeholder="Attendee emails (comma-separated)"
                  value={attendees}
                  onChange={(e) => setAttendees(e.target.value)}
                  className="text-xs h-8"
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={handleCreate}
                    disabled={isCreating}
                  >
                    {isCreating ? "Creating..." : "Create Event"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setShowForm(false)}
                  >
                    Cancel
                  </Button>
                </div>
                {error && (
                  <p className="text-xs text-red-500">{error}</p>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
