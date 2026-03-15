"use client";

import { useState, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { parseCodeBlocks } from "@/lib/parse-code-blocks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";

interface CodeFileViewerProps {
  content: string;
}

export function CodeFileViewer({ content }: CodeFileViewerProps) {
  const files = useMemo(() => parseCodeBlocks(content), [content]);
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (files.length === 0) {
    return (
      <div className="prose prose-sm dark:prose-invert max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  const selected = files[selectedIndex];

  return (
    <div className="space-y-2">
      {/* File list */}
      <div className="flex flex-wrap gap-1">
        {files.map((file, i) => (
          <button
            key={file.path}
            onClick={() => setSelectedIndex(i)}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors ${
              i === selectedIndex
                ? "border-primary bg-primary/10 text-foreground"
                : "border-transparent text-muted-foreground hover:bg-accent"
            }`}
          >
            <span className="truncate max-w-[200px]">{file.path}</span>
            {file.language && (
              <Badge variant="secondary" className="h-4 px-1 text-[10px]">
                {file.language}
              </Badge>
            )}
          </button>
        ))}
      </div>

      {/* Code display */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b px-3 py-1.5">
          <span className="text-xs text-muted-foreground font-mono">
            {selected.path}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={() => navigator.clipboard.writeText(selected.content)}
          >
            Copy
          </Button>
        </div>
        <ScrollArea className="max-h-80">
          <pre className="p-3 text-xs leading-relaxed">
            <code>{selected.content}</code>
          </pre>
        </ScrollArea>
      </Card>
    </div>
  );
}
