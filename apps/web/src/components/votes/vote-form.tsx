"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface VoteOption {
  id: string;
  label: string;
  description: string | null;
}

interface VoteFormProps {
  options: VoteOption[];
  onVote: (optionId: string, voterName: string, comment?: string) => void;
  isVoting?: boolean;
  disabled?: boolean;
}

export function VoteForm({ options, onVote, isVoting, disabled }: VoteFormProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [voterName, setVoterName] = useState("");
  const [comment, setComment] = useState("");

  const handleSubmit = () => {
    if (!selectedId || !voterName.trim()) return;
    onVote(selectedId, voterName.trim(), comment.trim() || undefined);
  };

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => !disabled && setSelectedId(opt.id)}
            disabled={disabled}
            className={cn(
              "w-full rounded-lg border p-3 text-left transition-colors",
              selectedId === opt.id
                ? "border-primary bg-primary/5"
                : "hover:bg-accent",
              disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            <p className="font-medium text-sm">{opt.label}</p>
            {opt.description && (
              <p className="mt-1 text-xs text-muted-foreground">
                {opt.description}
              </p>
            )}
          </button>
        ))}
      </div>

      <Input
        placeholder="Your name"
        value={voterName}
        onChange={(e) => setVoterName(e.target.value)}
        disabled={disabled}
        className="text-sm"
      />

      <Textarea
        placeholder="Comment (optional)"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        disabled={disabled}
        rows={2}
        className="text-sm"
      />

      <Button
        size="sm"
        onClick={handleSubmit}
        disabled={!selectedId || !voterName.trim() || isVoting || disabled}
        className="w-full"
      >
        {isVoting ? "Voting..." : "Cast Vote"}
      </Button>
    </div>
  );
}
