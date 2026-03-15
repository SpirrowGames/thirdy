"use client";

import { useState, useEffect } from "react";
import { usePullRequests } from "@/hooks/use-pull-requests";
import { useCodes } from "@/hooks/use-codes";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PRCard } from "./pr-card";

interface PRPanelProps {
  conversationId: string | null;
  preselectedCodeId?: string;
}

export function PRPanel({ conversationId, preselectedCodeId }: PRPanelProps) {
  const {
    pullRequests,
    isLoading,
    isCreating,
    progress,
    error,
    createPR,
    deletePR,
  } = usePullRequests(conversationId);

  const { codes } = useCodes(conversationId);
  const approvedCodes = codes.filter((c) => c.status === "approved");

  const [selectedCodeId, setSelectedCodeId] = useState<string>("");

  useEffect(() => {
    if (preselectedCodeId) {
      setSelectedCodeId(preselectedCodeId);
    }
  }, [preselectedCodeId]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b p-3">
        <Select value={selectedCodeId} onValueChange={setSelectedCodeId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select approved code..." />
          </SelectTrigger>
          <SelectContent>
            {approvedCodes.map((code) => (
              <SelectItem key={code.id} value={code.id}>
                Code {code.id.slice(0, 8)}...
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          onClick={() => createPR(selectedCodeId)}
          disabled={!conversationId || !selectedCodeId || isCreating}
          size="sm"
          className="w-full"
        >
          {isCreating ? "Creating PR..." : "Create Pull Request"}
        </Button>
      </div>

      {error && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isCreating && progress && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              {progress.step}
            </p>
            {progress.detail && (
              <p className="text-xs text-foreground">{progress.detail}</p>
            )}
            <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-primary" />
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : pullRequests.length === 0 && !isCreating ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No pull requests yet. Select approved code and click
            &quot;Create Pull Request&quot; to create a GitHub PR.
          </p>
        ) : (
          <div className="space-y-3">
            {pullRequests.map((pr) => (
              <PRCard key={pr.id} pr={pr} onDelete={deletePR} />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
