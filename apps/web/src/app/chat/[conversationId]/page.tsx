"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { useChat } from "@/hooks/use-chat";
import { useSpecs } from "@/hooks/use-specs";
import { useDesigns } from "@/hooks/use-designs";
import { useDecisions } from "@/hooks/use-decisions";
import { useTasks } from "@/hooks/use-tasks";
import { useCodes } from "@/hooks/use-codes";
import { usePullRequests } from "@/hooks/use-pull-requests";
import { useVoiceTranscripts } from "@/hooks/use-voice";
import { useGitHubIssues } from "@/hooks/use-github-issues";
import { useAudits } from "@/hooks/use-audits";
import { useWatches } from "@/hooks/use-watches";
import { useSpecReviews } from "@/hooks/use-spec-reviews";
import { MessageList } from "@/components/chat/message-list";
import { ChatInput } from "@/components/chat/chat-input";
import { SpecPanel } from "@/components/specs/spec-panel";
import { DesignPanel } from "@/components/designs/design-panel";
import { DecisionPanel } from "@/components/decisions/decision-panel";
import { TaskPanel } from "@/components/tasks/task-panel";
import { CodePanel } from "@/components/codes/code-panel";
import { PRPanel } from "@/components/pull-requests/pr-panel";
import { VoicePanel } from "@/components/voice/voice-panel";
import { IssuePanel } from "@/components/issues/issue-panel";
import { AuditPanel } from "@/components/audits/audit-panel";
import { WatchPanel } from "@/components/watches/watch-panel";
import { SpecReviewStandalonePanel } from "@/components/specs/spec-review-panel";
import { PipelineProgress } from "@/components/pipeline/pipeline-progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { RepoSelector } from "@/components/github/repo-selector";
import { useRepoContext } from "@/hooks/use-repo-context";
import { api } from "@/lib/api-client";
import type { ConversationRead } from "@/types/api";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params.conversationId as string;
  const [panelOpen, setPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("decisions");
  const [preselectedSpecId, setPreselectedSpecId] = useState<string>();
  const [preselectedDesignId, setPreselectedDesignId] = useState<string>();
  const [preselectedTaskId, setPreselectedTaskId] = useState<string>();
  const [preselectedCodeId, setPreselectedCodeId] = useState<string>();
  const [autoTrigger, setAutoTrigger] = useState(false);

  // Conversation data (for github_repo)
  const { data: conversation, mutate: mutateConversation } = useSWR<ConversationRead>(
    `/conversations/${conversationId}`,
  );

  const handleRepoChange = async (repo: string) => {
    await api.patch<ConversationRead>(`/conversations/${conversationId}`, {
      github_repo: repo || null,
    });
    await mutateConversation();
  };

  const { context: repoContext, isLoading: repoContextLoading, refresh: refreshRepoContext } = useRepoContext(
    conversation?.github_repo ?? null
  );

  // Resizable panel
  const PANEL_MIN = 280;
  const PANEL_MAX = 800;
  const PANEL_DEFAULT = 360;
  const [panelWidth, setPanelWidth] = useState(() => {
    if (typeof window === "undefined") return PANEL_DEFAULT;
    const saved = localStorage.getItem("thirdy-panel-width");
    return saved ? Math.max(PANEL_MIN, Math.min(PANEL_MAX, Number(saved))) : PANEL_DEFAULT;
  });
  const isDragging = useRef(false);

  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    const startX = e.clientX;
    const startWidth = panelWidth;
    const onMove = (ev: MouseEvent) => {
      const delta = startX - ev.clientX;
      const newWidth = Math.max(PANEL_MIN, Math.min(PANEL_MAX, startWidth + delta));
      setPanelWidth(newWidth);
    };
    const onUp = () => {
      isDragging.current = false;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, [panelWidth]);

  useEffect(() => {
    localStorage.setItem("thirdy-panel-width", String(panelWidth));
  }, [panelWidth]);

  const {
    messages,
    streamingContent,
    isStreaming,
    isLoadingMessages,
    error,
    sendMessage,
    stopStreaming,
  } = useChat({ conversationId, onConversationCreated: undefined });

  const { specs } = useSpecs(conversationId);
  const { designs } = useDesigns(conversationId);
  const { decisions } = useDecisions(conversationId);
  const { tasks } = useTasks(conversationId);
  const { codes } = useCodes(conversationId);
  const { pullRequests } = usePullRequests(conversationId);
  const { transcripts } = useVoiceTranscripts(conversationId);
  const { issues } = useGitHubIssues(conversationId);
  const { reports: auditReports } = useAudits(conversationId);
  const { reports: watchReports } = useWatches(conversationId);

  // Spec review: track for first spec (pulse badge when new reviews arrive)
  const firstSpecId = specs[0]?.id ?? null;
  const { reviews: specReviews } = useSpecReviews(conversationId, firstSpecId);

  // Background extraction status indicator
  // States: idle → analyzing (after chat done) → updated (spec changed) → idle (auto-dismiss)
  const [extractionStatus, setExtractionStatus] = useState<"idle" | "analyzing" | "updated">("idle");
  const extractionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // When streaming finishes (messages count increases from assistant), start "analyzing"
  const prevMessageCount = useRef(messages.length);
  useEffect(() => {
    const currentCount = messages.length;
    if (currentCount > prevMessageCount.current) {
      const lastMsg = messages[currentCount - 1];
      if (lastMsg?.role === "assistant") {
        setExtractionStatus("analyzing");
        // Auto-dismiss after 45s if no spec update detected
        if (extractionTimerRef.current) clearTimeout(extractionTimerRef.current);
        extractionTimerRef.current = setTimeout(() => {
          setExtractionStatus((s) => s === "analyzing" ? "idle" : s);
        }, 45000);
      }
    }
    prevMessageCount.current = currentCount;
  }, [messages.length, messages]);

  // Track spec auto-updates: detect when specs change while not on the specs tab
  const specFingerprint = specs.map((s) => `${s.id}:${s.updated_at}`).join(",");
  const prevSpecFingerprint = useRef(specFingerprint);
  const [specUpdated, setSpecUpdated] = useState(false);

  useEffect(() => {
    if (specFingerprint !== prevSpecFingerprint.current) {
      if (prevSpecFingerprint.current !== "") {
        if (activeTab !== "specs") setSpecUpdated(true);
        // Update extraction status
        if (extractionTimerRef.current) clearTimeout(extractionTimerRef.current);
        setExtractionStatus("updated");
        extractionTimerRef.current = setTimeout(() => setExtractionStatus("idle"), 5000);
      }
      prevSpecFingerprint.current = specFingerprint;
    }
  }, [specFingerprint, activeTab]);

  useEffect(() => {
    if (activeTab === "specs") {
      setSpecUpdated(false);
    }
  }, [activeTab]);

  // Track decision auto-updates
  const decisionFingerprint = decisions.map((d) => d.id).join(",");
  const prevDecisionFingerprint = useRef(decisionFingerprint);
  const [decisionUpdated, setDecisionUpdated] = useState(false);

  useEffect(() => {
    if (decisionFingerprint !== prevDecisionFingerprint.current) {
      if (prevDecisionFingerprint.current !== "" && activeTab !== "decisions") {
        setDecisionUpdated(true);
      }
      prevDecisionFingerprint.current = decisionFingerprint;
    }
  }, [decisionFingerprint, activeTab]);

  useEffect(() => {
    if (activeTab === "decisions") {
      setDecisionUpdated(false);
    }
  }, [activeTab]);

  // Track spec review updates — pulse badge when new completed reviews appear
  const reviewFingerprint = specReviews
    .filter((r) => r.status === "completed")
    .map((r) => `${r.id}:${r.updated_at}`)
    .join(",");
  const prevReviewFingerprint = useRef(reviewFingerprint);
  const [reviewUpdated, setReviewUpdated] = useState(false);

  useEffect(() => {
    if (reviewFingerprint !== prevReviewFingerprint.current) {
      if (prevReviewFingerprint.current !== "" && activeTab !== "review") {
        setReviewUpdated(true);
      }
      prevReviewFingerprint.current = reviewFingerprint;
    }
  }, [reviewFingerprint, activeTab]);

  useEffect(() => {
    if (activeTab === "review") {
      setReviewUpdated(false);
    }
  }, [activeTab]);

  const hasCompletedReviews = specReviews.some((r) => r.status === "completed");
  const hasReviewIssues = specReviews.some(
    (r) => r.status === "completed" && (r.summary?.total_issues ?? 0) > 0,
  );

  const hasApprovedSpec = specs.some((s) => s.status === "approved");
  const hasApprovedDesign = designs.some((d) => d.status === "approved");
  const pendingDecisions = decisions.filter((d) => d.status === "pending");
  const hasDecisionsResolved =
    decisions.length === 0 || pendingDecisions.length === 0;
  const hasGeneratedTasks = tasks.length > 0;
  const hasGeneratedCode = codes.length > 0;
  const hasPullRequests = pullRequests.length > 0;
  const hasVoiceTranscripts = transcripts.some((t) => t.status === "completed");
  const hasCreatedIssues = issues.some((i) => i.status === "created");
  const hasAuditReports = auditReports.some((r) => r.status === "completed");
  const hasWatchReports = watchReports.some((r) => r.status === "completed");

  const handleSpecApproved = (specId: string) => {
    setActiveTab("designs");
    setPreselectedSpecId(specId);
    setAutoTrigger(true);
  };

  const handleDesignApproved = (designId: string) => {
    if (pendingDecisions.length > 0) {
      setActiveTab("decisions");
    } else {
      setActiveTab("tasks");
      setAutoTrigger(true);
    }
    setPreselectedDesignId(designId);
  };

  // Auto-switch from decisions to tasks when all resolved
  useEffect(() => {
    if (activeTab === "decisions" && decisions.length > 0 && hasDecisionsResolved) {
      setActiveTab("tasks");
    }
  }, [activeTab, decisions.length, hasDecisionsResolved]);

  const handleTaskDone = (taskId: string) => {
    setActiveTab("codes");
    setPreselectedTaskId(taskId);
    setAutoTrigger(true);
  };

  const handleCodeApproved = (codeId: string) => {
    setActiveTab("prs");
    setPreselectedCodeId(codeId);
    setAutoTrigger(true);
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Chat area */}
      <div className="flex flex-1 flex-col min-h-0">
        <div className="flex items-center justify-between border-b px-4 py-3 md:pl-4 pl-12">
          <div className="flex items-center gap-2 min-w-0">
            <h1 className="text-sm font-medium truncate">
              {messages[0]?.content
                ? messages[0].content.slice(0, 60)
                : "Chat"}
            </h1>
            {conversation?.parent_id && (
              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                branch{conversation.branch_status === "merged" ? " (merged)" : ""}
              </span>
            )}
            {conversation?.parent_id && conversation?.branch_status === "active" && (
              <button
                onClick={async () => {
                  await api.post(`/conversations/${conversationId}/merge`, {});
                  await mutateConversation();
                }}
                className="shrink-0 rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-600 hover:bg-green-500/20 transition-colors"
              >
                Merge
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <RepoSelector
                value={conversation?.github_repo ?? null}
                onChange={handleRepoChange}
              />
            </div>
            {conversation?.github_repo && (
              <button
                onClick={() => refreshRepoContext()}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-accent transition-colors"
                title={
                  repoContextLoading
                    ? "Loading repo context..."
                    : repoContext
                      ? `Context loaded (${repoContext.file_count} files)`
                      : "Click to load repo context"
                }
              >
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                  repoContextLoading
                    ? "bg-yellow-500 animate-pulse"
                    : repoContext
                      ? "bg-green-500"
                      : "bg-muted-foreground/50"
                }`} />
                ctx
              </button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => setPanelOpen(!panelOpen)}
            >
              {panelOpen ? "Close Panel" : "Pipeline"}
            </Button>
          </div>
        </div>

        {isLoadingMessages ? (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-muted-foreground">Loading messages...</p>
          </div>
        ) : (
          <MessageList
            messages={messages}
            streamingContent={streamingContent}
            isStreaming={isStreaming}
          />
        )}

        {error && (
          <div className="mx-4 mb-2 rounded bg-destructive/10 p-2 text-sm text-destructive">
            {error}
          </div>
        )}

        {extractionStatus !== "idle" && (
          <div className="mx-4 mb-1 flex items-center gap-2 text-xs text-muted-foreground">
            {extractionStatus === "analyzing" && (
              <>
                <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-yellow-500" />
                仕様を分析中...
              </>
            )}
            {extractionStatus === "updated" && (
              <>
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                仕様が更新されました
              </>
            )}
          </div>
        )}

        <ChatInput onSend={sendMessage} disabled={isStreaming} isStreaming={isStreaming} onCancel={stopStreaming} />
      </div>

      {/* Right panel */}
      {panelOpen && (
        <aside className="hidden shrink-0 md:flex md:flex-col min-h-0 relative" style={{ width: panelWidth }}>
          {/* Drag handle */}
          <div
            onMouseDown={handleDragStart}
            className="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 z-10 border-l"
          />
          <PipelineProgress
            specsApproved={hasApprovedSpec}
            reviewCompleted={hasCompletedReviews}
            designsApproved={hasApprovedDesign}
            decisionsResolved={hasDecisionsResolved}
            tasksGenerated={hasGeneratedTasks}
            codesGenerated={hasGeneratedCode}
            prsCreated={hasPullRequests}
            voiceTranscribed={hasVoiceTranscripts}
            issuesCreated={hasCreatedIssues}
            auditsCompleted={hasAuditReports}
            watchesCompleted={hasWatchReports}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            reviewHasIssues={hasReviewIssues}
            reviewUpdated={reviewUpdated}
          />
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-1 min-h-0 flex-col">
            <TabsList className="mx-3 mt-1 flex flex-wrap w-full h-auto gap-0.5">
              <TabsTrigger value="specs">
                Specs
                {specUpdated && (
                  <span className="ml-1 inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                )}
              </TabsTrigger>
              <TabsTrigger value="review">
                Review
                {reviewUpdated && (
                  <span className="ml-1 inline-block h-2 w-2 rounded-full bg-orange-500 animate-pulse" />
                )}
                {!reviewUpdated && hasReviewIssues && (
                  <span className="ml-1 inline-block h-2 w-2 rounded-full bg-orange-500" />
                )}
              </TabsTrigger>
              <TabsTrigger value="designs">Designs</TabsTrigger>
              <TabsTrigger value="decisions">
                Decisions{pendingDecisions.length > 0 ? ` (${pendingDecisions.length})` : ""}
                {decisionUpdated && (
                  <span className="ml-1 inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                )}
              </TabsTrigger>
              <TabsTrigger value="tasks">Tasks</TabsTrigger>
              <TabsTrigger value="codes">Code</TabsTrigger>
              <TabsTrigger value="prs">PRs</TabsTrigger>
              <TabsTrigger value="voice">Voice</TabsTrigger>
              <TabsTrigger value="issues">Issues</TabsTrigger>
              <TabsTrigger value="audits">Audit</TabsTrigger>
              <TabsTrigger value="watches">Watch</TabsTrigger>
            </TabsList>
            <TabsContent value="specs" className="flex-1 overflow-y-auto">
              <SpecPanel
                conversationId={conversationId}
                onSpecApproved={handleSpecApproved}
              />
            </TabsContent>
            <TabsContent value="review" className="flex-1 overflow-y-auto">
              <SpecReviewStandalonePanel
                conversationId={conversationId}
                onSendToChat={sendMessage}
              />
            </TabsContent>
            <TabsContent value="designs" className="flex-1 overflow-y-auto">
              <DesignPanel
                conversationId={conversationId}
                onDesignApproved={handleDesignApproved}
                preselectedSpecId={preselectedSpecId}
                autoTrigger={autoTrigger && activeTab === "designs"}
                onAutoTriggered={() => setAutoTrigger(false)}
              />
            </TabsContent>
            <TabsContent value="decisions" className="flex-1 overflow-y-auto">
              <DecisionPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="tasks" className="flex-1 overflow-y-auto">
              <TaskPanel
                conversationId={conversationId}
                preselectedDesignId={preselectedDesignId}
                onTaskDone={handleTaskDone}
                autoTrigger={autoTrigger && activeTab === "tasks"}
                onAutoTriggered={() => setAutoTrigger(false)}
              />
            </TabsContent>
            <TabsContent value="codes" className="flex-1 overflow-y-auto">
              <CodePanel
                conversationId={conversationId}
                preselectedTaskId={preselectedTaskId}
                onCodeApproved={handleCodeApproved}
                autoTrigger={autoTrigger && activeTab === "codes"}
                onAutoTriggered={() => setAutoTrigger(false)}
              />
            </TabsContent>
            <TabsContent value="prs" className="flex-1 overflow-y-auto">
              <PRPanel
                conversationId={conversationId}
                preselectedCodeId={preselectedCodeId}
                autoTrigger={autoTrigger && activeTab === "prs"}
                onAutoTriggered={() => setAutoTrigger(false)}
              />
            </TabsContent>
            <TabsContent value="voice" className="flex-1 overflow-y-auto">
              <VoicePanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="issues" className="flex-1 overflow-y-auto">
              <IssuePanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="audits" className="flex-1 overflow-y-auto">
              <AuditPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="watches" className="flex-1 overflow-y-auto">
              <WatchPanel conversationId={conversationId} />
            </TabsContent>
          </Tabs>
        </aside>
      )}
    </div>
  );
}
