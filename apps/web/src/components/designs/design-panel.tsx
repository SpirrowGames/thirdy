"use client";

import { useState, useEffect } from "react";
import { useElapsedTime } from "@/hooks/use-elapsed-time";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useDesigns } from "@/hooks/use-designs";
import { useSpecs } from "@/hooks/use-specs";
import { api } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ErrorBanner } from "@/components/ui/error-banner";
import { DesignCard } from "./design-card";

interface DesignPanelProps {
  conversationId: string | null;
  onDesignApproved?: (designId: string) => void;
  preselectedSpecId?: string;
  autoTrigger?: boolean;
  onAutoTriggered?: () => void;
}

export function DesignPanel({ conversationId, onDesignApproved, preselectedSpecId, autoTrigger, onAutoTriggered }: DesignPanelProps) {
  const {
    designs,
    isLoading,
    isDecomposing,
    decompositionContent,
    error,
    decomposeDesign,
    updateDesign,
    deleteDesign,
  } = useDesigns(conversationId);

  const { specs } = useSpecs(conversationId);
  const approvedSpecs = specs.filter((s) => s.status === "approved");

  const [selectedSpecId, setSelectedSpecId] = useState<string>("");
  const [autoMode, setAutoMode] = useState(() => {
    if (typeof window === "undefined") return true;
    return localStorage.getItem("thirdy-auto-mode") !== "false";
  });
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const elapsed = useElapsedTime(isDecomposing);

  const toggleAutoMode = () => {
    const next = !autoMode;
    setAutoMode(next);
    localStorage.setItem("thirdy-auto-mode", String(next));
  };

  const triggerAutoPipeline = async (designId: string) => {
    setPipelineRunning(true);
    try {
      await api.post(`/designs/${designId}/auto-pipeline`, {});
    } catch {
      // errors will show via notifications
    }
    // Don't clear pipelineRunning — it stays until notifications arrive
  };

  useEffect(() => {
    if (preselectedSpecId) {
      setSelectedSpecId(preselectedSpecId);
    }
  }, [preselectedSpecId]);

  // Auto-trigger decomposition when autoTrigger is set
  useEffect(() => {
    if (autoTrigger && preselectedSpecId && !isDecomposing && conversationId) {
      decomposeDesign(preselectedSpecId);
      onAutoTriggered?.();
    }
  }, [autoTrigger, preselectedSpecId, isDecomposing, conversationId, decomposeDesign, onAutoTriggered]);

  return (
    <div className="flex h-full flex-col">
      <div className="space-y-2 border-b p-3">
        <Select value={selectedSpecId} onValueChange={setSelectedSpecId}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select approved spec..." />
          </SelectTrigger>
          <SelectContent>
            {approvedSpecs.map((spec) => (
              <SelectItem key={spec.id} value={spec.id}>
                {spec.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          onClick={() => decomposeDesign(selectedSpecId)}
          disabled={!conversationId || !selectedSpecId || isDecomposing}
          size="sm"
          className="w-full"
        >
          {isDecomposing ? "Decomposing..." : "Decompose"}
        </Button>
        <div className="flex items-center justify-between">
          <button
            onClick={toggleAutoMode}
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <span className={`inline-block h-2 w-2 rounded-full ${autoMode ? "bg-green-500" : "bg-muted-foreground/40"}`} />
            {autoMode ? "Auto" : "Manual"}
          </button>
          {autoMode && (
            <span className="text-[10px] text-muted-foreground">
              Approve後にTask→Code→PRまで自動実行
            </span>
          )}
          {pipelineRunning && (
            <span className="flex items-center gap-1 text-[10px] text-blue-500">
              <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
              Pipeline実行中...
            </span>
          )}
        </div>
      </div>

      {error && (
        <ErrorBanner
          error={error}
          onRetry={selectedSpecId ? () => decomposeDesign(selectedSpecId) : undefined}
          onDismiss={() => {}}
        />
      )}

      <ScrollArea className="flex-1 p-3">
        {isDecomposing && decompositionContent && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Decomposing...{elapsed && ` (${elapsed})`}
            </p>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {decompositionContent}
              </ReactMarkdown>
              <span className="inline-block h-4 w-1.5 animate-pulse bg-foreground/60" />
            </div>
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : designs.length === 0 && !isDecomposing ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No designs yet. Select an approved spec and click
            &quot;Decompose&quot; to generate a design document.
          </p>
        ) : (
          <div className="space-y-3">
            {designs.map((design) => (
              <DesignCard
                key={design.id}
                design={design}
                onStatusChange={(id, newStatus) => {
                  updateDesign(id, { status: newStatus });
                  if (newStatus === "approved") {
                    if (autoMode) {
                      triggerAutoPipeline(id);
                    }
                    onDesignApproved?.(id);
                  }
                }}
                onDelete={deleteDesign}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
