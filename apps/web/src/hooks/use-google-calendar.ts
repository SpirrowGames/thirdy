"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import type {
  CalendarEventCreate,
  CalendarEventPreset,
  CalendarEventResponse,
} from "@/types/api";
import { api, API_URL } from "@/lib/api-client";
import { getToken } from "@/lib/auth";

interface CalendarStatus {
  connected: boolean;
}

export function useGoogleCalendar() {
  const {
    data: status,
    mutate,
    isLoading,
  } = useSWR<CalendarStatus>("/auth/google/calendar/status");

  const [isCreating, setIsCreating] = useState(false);

  const connected = status?.connected ?? false;

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;
    // Browser redirect — can't use fetch for OAuth
    window.location.href = `${API_URL}/auth/google/calendar?token=${encodeURIComponent(token)}`;
  }, []);

  const disconnect = useCallback(async () => {
    await api.post("/auth/google/calendar/disconnect");
    await mutate({ connected: false }, { revalidate: true });
  }, [mutate]);

  const createEvent = useCallback(
    async (
      sessionId: string,
      preset: CalendarEventPreset,
      attendeeEmails: string[] = [],
      startTime?: string | null,
    ): Promise<CalendarEventResponse> => {
      setIsCreating(true);
      try {
        const body: CalendarEventCreate = {
          vote_session_id: sessionId,
          preset,
          attendee_emails: attendeeEmails,
          start_time: startTime ?? null,
        };
        return await api.post<CalendarEventResponse>(
          `/vote-sessions/${sessionId}/calendar-event`,
          body,
        );
      } finally {
        setIsCreating(false);
      }
    },
    [],
  );

  return {
    connected,
    isLoading,
    isCreating,
    connect,
    disconnect,
    createEvent,
    mutate,
  };
}
