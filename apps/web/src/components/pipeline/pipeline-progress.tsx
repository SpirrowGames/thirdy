"use client";

interface PipelineStep {
  key: string;
  label: string;
  completed: boolean;
}

interface PipelineProgressProps {
  specsApproved: boolean;
  reviewCompleted: boolean;
  designsApproved: boolean;
  decisionsResolved: boolean;
  tasksGenerated: boolean;
  codesGenerated: boolean;
  prsCreated: boolean;
  voiceTranscribed: boolean;
  issuesCreated: boolean;
  auditsCompleted: boolean;
  watchesCompleted: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  reviewHasIssues?: boolean;
  reviewUpdated?: boolean;
}

export function PipelineProgress({
  specsApproved,
  reviewCompleted,
  designsApproved,
  decisionsResolved,
  tasksGenerated,
  codesGenerated,
  prsCreated,
  voiceTranscribed,
  issuesCreated,
  auditsCompleted,
  watchesCompleted,
  activeTab,
  onTabChange,
  reviewHasIssues,
  reviewUpdated,
}: PipelineProgressProps) {
  const steps: PipelineStep[] = [
    { key: "specs", label: "Spec", completed: specsApproved },
    { key: "review", label: "Review", completed: reviewCompleted },
    { key: "designs", label: "Design", completed: designsApproved },
    { key: "decisions", label: "Decisions", completed: decisionsResolved },
    { key: "tasks", label: "Tasks", completed: tasksGenerated },
    { key: "codes", label: "Code", completed: codesGenerated },
    { key: "prs", label: "PR", completed: prsCreated },
    { key: "voice", label: "Voice", completed: voiceTranscribed },
    { key: "issues", label: "Issues", completed: issuesCreated },
    { key: "audits", label: "Audit", completed: auditsCompleted },
    { key: "watches", label: "Watch", completed: watchesCompleted },
  ];

  return (
    <div className="flex flex-wrap items-center justify-center gap-1 px-3 pt-3 pb-1">
      {steps.map((step, i) => {
        const isActive = step.key === activeTab;
        return (
          <button
            key={step.key}
            onClick={() => onTabChange(step.key)}
            className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-xs whitespace-nowrap transition-colors ${
              isActive
                ? "bg-accent text-accent-foreground font-medium"
                : "hover:bg-accent/50 text-muted-foreground"
            }`}
          >
            <span
              className={`inline-block h-2 w-2 shrink-0 rounded-full ${
                step.key === "review" && reviewUpdated
                  ? "bg-orange-500 animate-pulse"
                  : step.key === "review" && reviewHasIssues
                    ? "bg-orange-500"
                    : step.completed
                      ? "bg-green-500"
                      : isActive
                        ? "bg-foreground"
                        : "border border-muted-foreground/50"
              }`}
            />
            {step.label}
          </button>
        );
      })}
    </div>
  );
}
