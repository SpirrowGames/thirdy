"use client";

interface PipelineStep {
  key: string;
  label: string;
  completed: boolean;
}

interface PipelineProgressProps {
  specsApproved: boolean;
  designsApproved: boolean;
  decisionsResolved: boolean;
  tasksGenerated: boolean;
  codesGenerated: boolean;
  prsCreated: boolean;
  voiceTranscribed: boolean;
  issuesCreated: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function PipelineProgress({
  specsApproved,
  designsApproved,
  decisionsResolved,
  tasksGenerated,
  codesGenerated,
  prsCreated,
  voiceTranscribed,
  issuesCreated,
  activeTab,
  onTabChange,
}: PipelineProgressProps) {
  const steps: PipelineStep[] = [
    { key: "specs", label: "Spec", completed: specsApproved },
    { key: "designs", label: "Design", completed: designsApproved },
    { key: "decisions", label: "Decisions", completed: decisionsResolved },
    { key: "tasks", label: "Tasks", completed: tasksGenerated },
    { key: "codes", label: "Code", completed: codesGenerated },
    { key: "prs", label: "PR", completed: prsCreated },
    { key: "voice", label: "Voice", completed: voiceTranscribed },
    { key: "issues", label: "Issues", completed: issuesCreated },
  ];

  return (
    <div className="flex items-center justify-center gap-1 px-3 pt-3 pb-1">
      {steps.map((step, i) => {
        const isActive = step.key === activeTab;
        return (
          <div key={step.key} className="flex items-center">
            {i > 0 && (
              <div
                className={`mx-1 h-px w-4 ${
                  steps[i - 1].completed
                    ? "bg-green-500"
                    : "bg-muted-foreground/30"
                }`}
              />
            )}
            <button
              onClick={() => onTabChange(step.key)}
              className={`flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs transition-colors ${
                isActive
                  ? "bg-accent text-accent-foreground font-medium"
                  : "hover:bg-accent/50 text-muted-foreground"
              }`}
            >
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  step.completed
                    ? "bg-green-500"
                    : isActive
                      ? "bg-foreground"
                      : "border border-muted-foreground/50"
                }`}
              />
              {step.label}
            </button>
          </div>
        );
      })}
    </div>
  );
}
