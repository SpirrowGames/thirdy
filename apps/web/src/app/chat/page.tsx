"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { useChat } from "@/hooks/use-chat";
import { useConversations } from "@/hooks/use-conversations";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";

export default function NewChatPage() {
  const router = useRouter();
  const { mutate: refreshConversations } = useConversations();

  const onConversationCreated = useCallback(
    (conversationId: string) => {
      refreshConversations();
      router.replace(`/chat/${conversationId}`);
    },
    [router, refreshConversations],
  );

  const {
    messages,
    streamingContent,
    isStreaming,
    error,
    sendMessage,
  } = useChat({
    conversationId: null,
    onConversationCreated,
  });

  return (
    <div className="flex flex-1 flex-col">
      <div className="flex items-center border-b px-4 py-3 md:pl-4 pl-12">
        <h1 className="text-sm font-medium">New Chat</h1>
      </div>

      <MessageList
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
      />

      {error && (
        <div className="mx-4 mb-2 rounded bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
