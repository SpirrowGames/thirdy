"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useGitHubIssues } from "@/hooks/use-github-issues";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { IssueCard } from "./issue-card";

interface IssuePanelProps {
  conversationId: string | null;
}

export function IssuePanel({ conversationId }: IssuePanelProps) {
  const {
    issues,
    isLoading,
    isStructuring,
    isCreating,
    structuredPreview,
    streamingContent,
    issueError,
    structureIssue,
    createIssue,
    updateIssue,
    deleteIssue,
    stopStream,
  } = useGitHubIssues(conversationId);

  const [inputText, setInputText] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editBody, setEditBody] = useState("");

  const handleStructure = () => {
    if (!inputText.trim()) return;
    structureIssue(inputText.trim());
  };

  const handleCreate = () => {
    if (!structuredPreview) return;
    // Save any edits before creating
    if (editTitle !== structuredPreview.title || editBody !== structuredPreview.body) {
      updateIssue(structuredPreview.issue_id, {
        title: editTitle,
        body: editBody,
      }).then(() => {
        createIssue(structuredPreview.issue_id);
      });
    } else {
      createIssue(structuredPreview.issue_id);
    }
  };

  // When preview arrives, sync edit fields
  const previewId = structuredPreview?.issue_id;
  const [lastPreviewId, setLastPreviewId] = useState<string | null>(null);
  if (previewId && previewId !== lastPreviewId) {
    setLastPreviewId(previewId);
    setEditTitle(structuredPreview.title);
    setEditBody(structuredPreview.body);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-3 space-y-2">
        <textarea
          className="w-full rounded-md border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-ring"
          rows={3}
          placeholder="Describe your issue in natural language..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={isStructuring}
        />
        <div className="flex gap-2">
          <Button
            size="sm"
            className="flex-1"
            onClick={handleStructure}
            disabled={!conversationId || !inputText.trim() || isStructuring}
          >
            {isStructuring ? "Structuring..." : "Structure Issue"}
          </Button>
          {isStructuring && (
            <Button size="sm" variant="ghost" onClick={stopStream}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {issueError && (
        <div className="border-b bg-destructive/10 p-3 text-sm text-destructive">
          {issueError}
        </div>
      )}

      <ScrollArea className="flex-1 p-3">
        {/* Streaming LLM response */}
        {isStructuring && streamingContent && (
          <div className="mb-4 rounded-lg border bg-muted/50 p-3">
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Structuring...
            </p>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {streamingContent}
              </ReactMarkdown>
              <span className="inline-block h-4 w-1.5 animate-pulse bg-foreground/60" />
            </div>
          </div>
        )}

        {/* Structured preview with inline editing */}
        {structuredPreview && !isStructuring && (
          <div className="mb-4 rounded-lg border bg-accent/30 p-3 space-y-3">
            <p className="text-xs font-medium text-muted-foreground">
              Preview
            </p>
            <input
              className="w-full rounded-md border bg-background px-2 py-1 text-sm font-medium focus:outline-none focus:ring-1 focus:ring-ring"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
            />
            <textarea
              className="w-full rounded-md border bg-background px-2 py-1 text-xs resize-none focus:outline-none focus:ring-1 focus:ring-ring"
              rows={6}
              value={editBody}
              onChange={(e) => setEditBody(e.target.value)}
            />
            {structuredPreview.labels.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {structuredPreview.labels.map((label) => (
                  <Badge key={label} variant="outline" className="text-[10px]">
                    {label}
                  </Badge>
                ))}
              </div>
            )}
            <Button
              size="sm"
              className="w-full"
              onClick={handleCreate}
              disabled={isCreating}
            >
              {isCreating ? "Creating on GitHub..." : "Create on GitHub"}
            </Button>
          </div>
        )}

        {/* Issue list */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : issues.length === 0 && !structuredPreview && !isStructuring ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No issues yet. Describe a problem above and click &quot;Structure
            Issue&quot; to create one.
          </p>
        ) : (
          <div className="space-y-3">
            {issues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                onDelete={deleteIssue}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
