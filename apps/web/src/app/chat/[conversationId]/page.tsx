"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useChat } from "@/hooks/use-chat";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { SpecPanel } from "@/components/specs/spec-panel";
import { DesignPanel } from "@/components/designs/design-panel";
import { DecisionPanel } from "@/components/decisions/decision-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params.conversationId as string;
  const [panelOpen, setPanelOpen] = useState(false);

  const {
    messages,
    streamingContent,
    isStreaming,
    isLoadingMessages,
    error,
    sendMessage,
  } = useChat({ conversationId, onConversationCreated: undefined });

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3 md:pl-4 pl-12">
          <h1 className="text-sm font-medium truncate">
            {messages[0]?.content
              ? messages[0].content.slice(0, 60)
              : "Chat"}
          </h1>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setPanelOpen(!panelOpen)}
          >
            {panelOpen ? "Close Panel" : "Specs & Designs"}
          </Button>
        </div>

        {isLoadingMessages ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-muted-foreground">Loading messages...</p>
          </div>
        ) : (
          <MessageList
            messages={messages}
            streamingContent={streamingContent}
            isStreaming={isStreaming}
          />
        )}

        {error && (
          <div className="mx-4 mb-2 rounded bg-destructive/10 p-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>

      {/* Right panel */}
      {panelOpen && (
        <aside className="hidden w-[360px] shrink-0 border-l md:flex md:flex-col">
          <Tabs defaultValue="specs" className="flex h-full flex-col">
            <TabsList className="mx-3 mt-3">
              <TabsTrigger value="specs">Specs</TabsTrigger>
              <TabsTrigger value="designs">Designs</TabsTrigger>
              <TabsTrigger value="decisions">Decisions</TabsTrigger>
            </TabsList>
            <TabsContent value="specs" className="flex-1 overflow-hidden">
              <SpecPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="designs" className="flex-1 overflow-hidden">
              <DesignPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="decisions" className="flex-1 overflow-hidden">
              <DecisionPanel conversationId={conversationId} />
            </TabsContent>
          </Tabs>
        </aside>
      )}
    </div>
  );
}
