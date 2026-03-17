"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { api } from "@/lib/api-client";

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export function useNotifications() {
  const { data: notifications, error, mutate } = useSWR<NotificationItem[]>(
    "/notifications",
    { refreshInterval: 30000 },
  );

  const { data: countData } = useSWR<{ unread_count: number }>(
    "/notifications/count",
    { refreshInterval: 15000 },
  );

  const markRead = useCallback(async (id: string) => {
    await api.patch(`/notifications/${id}/read`, {});
    await mutate();
  }, [mutate]);

  const markAllRead = useCallback(async () => {
    await api.post("/notifications/read-all");
    await mutate();
  }, [mutate]);

  const dismiss = useCallback(async (id: string) => {
    await api.del(`/notifications/${id}`);
    await mutate();
  }, [mutate]);

  return {
    notifications: notifications ?? [],
    unreadCount: countData?.unread_count ?? 0,
    isLoading: !notifications && !error,
    markRead,
    markAllRead,
    dismiss,
  };
}
