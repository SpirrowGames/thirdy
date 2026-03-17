"use client";

import { useAuth } from "@/hooks/use-auth";
import { useDashboardSummary, useDashboardTasks, useDashboardPRs } from "@/hooks/use-dashboard";
import Link from "next/link";

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-500/10 text-red-500",
    high: "bg-orange-500/10 text-orange-500",
    medium: "bg-blue-500/10 text-blue-500",
    low: "bg-gray-500/10 text-gray-500",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[priority] ?? colors.medium}`}>
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-500/10 text-yellow-600",
    in_progress: "bg-blue-500/10 text-blue-500",
    done: "bg-green-500/10 text-green-500",
    created: "bg-green-500/10 text-green-500",
    merged: "bg-purple-500/10 text-purple-500",
    failed: "bg-red-500/10 text-red-500",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[status] ?? "bg-gray-500/10 text-gray-500"}`}>
      {status}
    </span>
  );
}

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const { summary, isLoading: summaryLoading } = useDashboardSummary();
  const { tasks } = useDashboardTasks();
  const { prs } = useDashboardPRs();

  if (authLoading || !isAuthenticated) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <Link href="/chat" className="text-sm text-muted-foreground hover:text-foreground">
          Back to Chat
        </Link>
      </div>

      {/* Summary Cards */}
      {summaryLoading || !summary ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
          <StatCard label="Conversations" value={summary.conversation_count} />
          <StatCard label="Specs" value={summary.specs.total} sub={`${summary.specs.approved} approved`} />
          <StatCard label="Designs" value={summary.designs.total} sub={`${summary.designs.approved} approved`} />
          <StatCard label="Tasks" value={summary.tasks.total} sub={`${summary.tasks.done} done`} />
          <StatCard label="Code" value={summary.codes.total} sub={`${summary.codes.approved} approved`} />
          <StatCard label="PRs" value={summary.prs.total} sub={`${summary.prs.merged} merged`} />
        </div>
      )}

      {/* Repo Groups */}
      {summary && summary.repos.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-3 text-sm font-semibold">Repositories</h2>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
            {summary.repos.map((repo, i) => (
              <div key={i} className="rounded-lg border p-3">
                <p className="text-sm font-medium truncate">
                  {repo.github_repo ?? "No repository"}
                </p>
                <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                  <span>{repo.conversation_count} convs</span>
                  <span>{repo.spec_count} specs</span>
                  <span>{repo.task_count} tasks</span>
                  <span>{repo.pr_count} PRs</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tasks */}
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold">Recent Tasks</h2>
        {tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tasks yet</p>
        ) : (
          <div className="space-y-1">
            {tasks.slice(0, 20).map((task) => (
              <Link
                key={task.id}
                href={`/chat/${task.conversation_id}`}
                className="flex items-center gap-2 rounded-lg border px-3 py-2 hover:bg-accent transition-colors"
              >
                <PriorityBadge priority={task.priority} />
                <StatusBadge status={task.status} />
                <span className="flex-1 truncate text-sm">{task.title}</span>
                {task.github_repo && (
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {task.github_repo.split("/").pop()}
                  </span>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* PRs */}
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold">Recent Pull Requests</h2>
        {prs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No pull requests yet</p>
        ) : (
          <div className="space-y-1">
            {prs.slice(0, 10).map((pr) => (
              <div
                key={pr.id}
                className="flex items-center gap-2 rounded-lg border px-3 py-2"
              >
                <StatusBadge status={pr.status} />
                <span className="flex-1 truncate text-sm">{pr.title}</span>
                {pr.pr_url && (
                  <a
                    href={pr.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-xs text-blue-500 hover:underline"
                  >
                    #{pr.pr_number}
                  </a>
                )}
                {pr.github_repo && (
                  <span className="shrink-0 text-[10px] text-muted-foreground">
                    {pr.github_repo.split("/").pop()}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
