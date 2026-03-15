"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { MessageRead } from "@/types/api";
import { MessageBubble } from "./message-bubble";
import { StreamingMessage } from "./streaming-message";

interface MessageListProps {
  messages: MessageRead[];
  streamingContent: string;
  isStreaming: boolean;
}

export function MessageList({
  messages,
  streamingContent,
  isStreaming,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Start a conversation by sending a message.</p>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 px-4">
      <div className="mx-auto max-w-3xl space-y-4 py-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && <StreamingMessage content={streamingContent} />}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
