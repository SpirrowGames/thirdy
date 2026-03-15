"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import useSWR from "swr";
import type {
  MeetingSuggestion,
  PublicVoteSession,
  VoteSessionRead,
  VoteTally,
} from "@/types/api";
import { api, API_URL } from "@/lib/api-client";

// --- Authenticated hook for session management ---

export function useVoteSessions(decisionId: string | null) {
  const {
    data: sessions,
    mutate,
    isLoading,
  } = useSWR<VoteSessionRead[]>(
    decisionId ? `/decisions/${decisionId}/vote-sessions` : null,
  );

  const createSession = async (deadline?: string | null) => {
    if (!decisionId) return;
    const created = await api.post<VoteSessionRead>(
      `/decisions/${decisionId}/vote-sessions`,
      { decision_point_id: decisionId, deadline: deadline ?? null },
    );
    await mutate();
    return created;
  };

  const closeSession = async (sessionId: string) => {
    const closed = await api.post<VoteSessionRead>(
      `/vote-sessions/${sessionId}/close`,
      {},
    );
    await mutate();
    return closed;
  };

  const getMeetingSuggestion = async (sessionId: string) => {
    return api.get<MeetingSuggestion>(
      `/vote-sessions/${sessionId}/meeting-suggestion`,
    );
  };

  return {
    sessions: sessions ?? [],
    isLoading,
    createSession,
    closeSession,
    getMeetingSuggestion,
    mutate,
  };
}

// --- Public hook for voting + SSE realtime ---

function getVoterToken(): string {
  const key = "thirdy_voter_token";
  let token = localStorage.getItem(key);
  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem(key, token);
  }
  return token;
}

export function usePublicVote(shareToken: string) {
  const [session, setSession] = useState<PublicVoteSession | null>(null);
  const [tally, setTally] = useState<VoteTally[]>([]);
  const [totalVotes, setTotalVotes] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isVoting, setIsVoting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Fetch initial data
  useEffect(() => {
    if (!shareToken) return;
    setIsLoading(true);

    fetch(`${API_URL}/vote-sessions/${shareToken}/public`)
      .then((res) => {
        if (!res.ok) throw new Error("Session not found");
        return res.json();
      })
      .then((data: PublicVoteSession) => {
        setSession(data);
        setTally(data.session.tally);
        setTotalVotes(data.session.total_votes);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, [shareToken]);

  // SSE connection
  useEffect(() => {
    if (!shareToken) return;

    const es = new EventSource(
      `${API_URL}/vote-sessions/${shareToken}/stream`,
    );
    eventSourceRef.current = es;

    es.addEventListener("tally_update", (e) => {
      const data = JSON.parse(e.data);
      setTally(data.tally);
      setTotalVotes(data.total_votes);
    });

    es.addEventListener("session_closed", (e) => {
      const data = JSON.parse(e.data);
      setSession((prev) =>
        prev
          ? { ...prev, session: { ...prev.session, status: data.status } }
          : prev,
      );
    });

    es.addEventListener("error", () => {
      // SSE reconnect is automatic
    });

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [shareToken]);

  const castVote = useCallback(
    async (optionId: string, voterName: string, comment?: string) => {
      if (!shareToken) return;
      setIsVoting(true);
      setError(null);

      try {
        const res = await fetch(
          `${API_URL}/vote-sessions/${shareToken}/votes`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              option_id: optionId,
              voter_name: voterName,
              voter_token: getVoterToken(),
              comment: comment || null,
            }),
          },
        );
        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: "Vote failed" }));
          throw new Error(body.detail);
        }
        const data = await res.json();
        setTally(data.tally);
        setTotalVotes(data.total_votes);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setIsVoting(false);
      }
    },
    [shareToken],
  );

  return {
    session,
    decision: session?.decision ?? null,
    tally,
    totalVotes,
    castVote,
    isLoading,
    isVoting,
    error,
  };
}
