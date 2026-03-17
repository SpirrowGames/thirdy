"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useDesigns } from "@/hooks/use-designs";
import { useSpecs } from "@/hooks/use-specs";
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
              Decomposing...
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
                onStatusChange={(id, status) => {
                  updateDesign(id, { status });
                  if (status === "approved" && onDesignApproved) {
                    onDesignApproved(id);
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
