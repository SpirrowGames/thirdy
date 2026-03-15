"use client";

import useSWR from "swr";
import type { ConversationRead } from "@/types/api";
import { api } from "@/lib/api-client";

export function useConversations() {
  const { data, error, isLoading, mutate } = useSWR<ConversationRead[]>(
    "/conversations",
  );

  const createConversation = async (title?: string) => {
    const conv = await api.post<ConversationRead>("/conversations", { title });
    await mutate();
    return conv;
  };

  const updateConversation = async (id: string, title: string) => {
    const conv = await api.patch<ConversationRead>(`/conversations/${id}`, {
      title,
    });
    await mutate();
    return conv;
  };

  const deleteConversation = async (id: string) => {
    await api.del(`/conversations/${id}`);
    await mutate();
  };

  return {
    conversations: data ?? [],
    error,
    isLoading,
    mutate,
    createConversation,
    updateConversation,
    deleteConversation,
  };
}
