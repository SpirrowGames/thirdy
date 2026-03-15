"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ConversationRead } from "@/types/api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface ConversationItemProps {
  conversation: ConversationRead;
  onDelete: (id: string) => void;
}

export function ConversationItem({
  conversation,
  onDelete,
}: ConversationItemProps) {
  const pathname = usePathname();
  const isActive = pathname === `/chat/${conversation.id}`;

  return (
    <div
      className={cn(
        "group flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent",
        isActive && "bg-accent",
      )}
    >
      <Link
        href={`/chat/${conversation.id}`}
        className="flex-1 truncate"
      >
        {conversation.title || "Untitled"}
      </Link>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
        onClick={(e) => {
          e.preventDefault();
          onDelete(conversation.id);
        }}
      >
        <span className="text-xs">×</span>
      </Button>
    </div>
  );
}
