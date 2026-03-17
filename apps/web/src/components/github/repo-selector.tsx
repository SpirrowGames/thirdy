"use client";

import { useState } from "react";
import { useGitHubRepos } from "@/hooks/use-github-repos";
import { Button } from "@/components/ui/button";

interface RepoSelectorProps {
  value: string | null;
  onChange: (repo: string) => void;
}

export function RepoSelector({ value, onChange }: RepoSelectorProps) {
  const { repos, isLoading, error, createRepo, mutate, config } = useGitHubRepos();
  const disabled = !config.configured;
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newRepoName, setNewRepoName] = useState("");
  const [newRepoDesc, setNewRepoDesc] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [filter, setFilter] = useState("");

  const filteredRepos = repos.filter((r) =>
    r.name.toLowerCase().includes(filter.toLowerCase())
  );

  const handleCreate = async () => {
    if (!newRepoName.trim()) return;
    setIsCreating(true);
    try {
      const repo = await createRepo({
        name: newRepoName.trim(),
        description: newRepoDesc.trim(),
        private: true,
      });
      onChange(repo.full_name);
      setCreating(false);
      setNewRepoName("");
      setNewRepoDesc("");
      setOpen(false);
    } catch {
      // error handled by SWR
    } finally {
      setIsCreating(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => {
          if (disabled) return;
          setOpen(true);
          mutate();
        }}
        disabled={disabled}
        className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors truncate max-w-[200px] ${
          disabled
            ? "text-muted-foreground/50 cursor-not-allowed"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground cursor-pointer"
        }`}
        title={
          disabled
            ? "GitHub組織(GITHUB_ORG)が設定されていないため無効です"
            : value || "Set repository"
        }
      >
        <svg className="h-3.5 w-3.5 shrink-0" viewBox="0 0 16 16" fill="currentColor">
          <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
        </svg>
        {value ? value.split("/").pop() : "No repo"}
      </button>
    );
  }

  return (
    <div className="absolute top-full right-0 z-50 mt-1 w-72 rounded-lg border bg-popover p-2 shadow-lg">
      {!creating ? (
        <>
          <input
            type="text"
            placeholder="Filter repositories..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="mb-2 w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ring"
            autoFocus
          />
          <div className="max-h-48 overflow-y-auto space-y-0.5">
            {isLoading && (
              <p className="px-2 py-1 text-xs text-muted-foreground">Loading...</p>
            )}
            {error && (
              <p className="px-2 py-1 text-xs text-destructive">Failed to load repos</p>
            )}
            {/* Unset option */}
            <button
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1 text-xs hover:bg-accent text-muted-foreground"
            >
              No repository
            </button>
            {filteredRepos.map((repo) => (
              <button
                key={repo.full_name}
                onClick={() => {
                  onChange(repo.full_name);
                  setOpen(false);
                }}
                className={`flex w-full items-center gap-2 rounded px-2 py-1 text-xs hover:bg-accent ${
                  value === repo.full_name ? "bg-accent font-medium" : ""
                }`}
              >
                <span className="truncate">{repo.name}</span>
                {repo.private && (
                  <span className="shrink-0 rounded bg-muted px-1 text-[10px] text-muted-foreground">
                    private
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="mt-2 flex gap-1 border-t pt-2">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 flex-1 text-xs"
              onClick={() => setCreating(true)}
            >
              + New Repo
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setOpen(false)}
            >
              Close
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="mb-2 text-xs font-medium">Create new repository</p>
          <input
            type="text"
            placeholder="Repository name"
            value={newRepoName}
            onChange={(e) => setNewRepoName(e.target.value)}
            className="mb-1 w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ring"
            autoFocus
          />
          <input
            type="text"
            placeholder="Description (optional)"
            value={newRepoDesc}
            onChange={(e) => setNewRepoDesc(e.target.value)}
            className="mb-2 w-full rounded border bg-background px-2 py-1 text-xs outline-none focus:ring-1 focus:ring-ring"
          />
          <div className="flex gap-1">
            <Button
              size="sm"
              className="h-6 flex-1 text-xs"
              onClick={handleCreate}
              disabled={!newRepoName.trim() || isCreating}
            >
              {isCreating ? "Creating..." : "Create"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={() => setCreating(false)}
            >
              Back
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
