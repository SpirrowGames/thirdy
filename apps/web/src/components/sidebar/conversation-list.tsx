"use client";

import Link from "next/link";
import { useConversations } from "@/hooks/use-conversations";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ConversationItem } from "./conversation-item";

export function ConversationList() {
  const { conversations, isLoading, deleteConversation } = useConversations();

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Link href="/chat">
          <Button variant="outline" className="w-full">
            + New Chat
          </Button>
        </Link>
      </div>
      <ScrollArea className="flex-1 px-2">
        {isLoading ? (
          <div className="space-y-2 p-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-8 animate-pulse rounded bg-muted"
              />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <p className="p-4 text-center text-sm text-muted-foreground">
            No conversations yet.
          </p>
        ) : (
          <div className="space-y-1 pb-4">
            {conversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                onDelete={deleteConversation}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
