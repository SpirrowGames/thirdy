"use client";

import { useState } from "react";
import type { DecisionOptionRead } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface OptionSelectorProps {
  options: DecisionOptionRead[];
  onResolve: (optionId: string, note: string) => void;
  onDismiss: (note: string) => void;
}

export function OptionSelector({
  options,
  onResolve,
  onDismiss,
}: OptionSelectorProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [note, setNote] = useState("");

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => setSelectedId(opt.id)}
            className={cn(
              "w-full rounded-lg border p-3 text-left transition-colors",
              selectedId === opt.id
                ? "border-primary bg-primary/5"
                : "hover:bg-accent",
            )}
          >
            <p className="font-medium text-sm">{opt.label}</p>
            {opt.description && (
              <p className="mt-1 text-xs text-muted-foreground">
                {opt.description}
              </p>
            )}
            {opt.pros.length > 0 && (
              <div className="mt-2 space-y-0.5">
                {opt.pros.map((pro, i) => (
                  <p key={i} className="text-xs text-green-600">
                    + {pro}
                  </p>
                ))}
              </div>
            )}
            {opt.cons.length > 0 && (
              <div className="mt-1 space-y-0.5">
                {opt.cons.map((con, i) => (
                  <p key={i} className="text-xs text-red-600">
                    − {con}
                  </p>
                ))}
              </div>
            )}
          </button>
        ))}
      </div>

      <Textarea
        placeholder="Resolution note (optional)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        className="text-sm"
      />

      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => selectedId && onResolve(selectedId, note)}
          disabled={!selectedId}
          className="flex-1"
        >
          Resolve
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onDismiss(note)}
        >
          Dismiss
        </Button>
      </div>
    </div>
  );
}
