"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSpecs } from "@/hooks/use-specs";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SpecPreview } from "./spec-preview";

interface SpecPanelProps {
  conversationId: string | null;
  onSpecApproved?: (specId: string) => void;
}

export function SpecPanel({ conversationId, onSpecApproved }: SpecPanelProps) {
  const {
    specs,
    isLoading,
    isExtracting,
    extractionContent,
    error,
    extractSpec,
    updateSpec,
    deleteSpec,
  } = useSpecs(conversationId);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-3">
        <Button
          onClick={extractSpec}
          disabled={!conversationId || isExtracting}
          size="sm"
          className="w-full"
        >
          {isExtracting ? "Extracting..." : "Extract Spec"}
        </Button>
      </div>

      {error && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {isExtracting && extractionContent && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Extracting...
            </p>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {extractionContent}
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
        ) : specs.length === 0 && !isExtracting ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No specifications yet. Click &quot;Extract Spec&quot; to generate
            one from the conversation.
          </p>
        ) : (
          <div className="space-y-3">
            {specs.map((spec) => (
              <SpecPreview
                key={spec.id}
                spec={spec}
                onStatusChange={(id, status) => {
                  updateSpec(id, { status });
                  if (status === "approved" && onSpecApproved) {
                    onSpecApproved(id);
                  }
                }}
                onDelete={deleteSpec}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
