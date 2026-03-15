"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
import { PipelineProgress } from "@/components/pipeline/pipeline-progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params.conversationId as string;
  const [panelOpen, setPanelOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("specs");
  const [preselectedSpecId, setPreselectedSpecId] = useState<string>();
  const [preselectedDesignId, setPreselectedDesignId] = useState<string>();
  const [preselectedTaskId, setPreselectedTaskId] = useState<string>();
  const [preselectedCodeId, setPreselectedCodeId] = useState<string>();

  const {
    messages,
    streamingContent,
    isStreaming,
    isLoadingMessages,
    error,
    sendMessage,
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
  };

  const handleDesignApproved = (designId: string) => {
    if (pendingDecisions.length > 0) {
      setActiveTab("decisions");
    } else {
      setActiveTab("tasks");
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
  };

  const handleCodeApproved = (codeId: string) => {
    setActiveTab("prs");
    setPreselectedCodeId(codeId);
  };

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Chat area */}
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3 md:pl-4 pl-12">
          <h1 className="text-sm font-medium truncate">
            {messages[0]?.content
              ? messages[0].content.slice(0, 60)
              : "Chat"}
          </h1>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setPanelOpen(!panelOpen)}
          >
            {panelOpen ? "Close Panel" : "Pipeline"}
          </Button>
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

        <ChatInput onSend={sendMessage} disabled={isStreaming} />
      </div>

      {/* Right panel */}
      {panelOpen && (
        <aside className="hidden w-[360px] shrink-0 border-l md:flex md:flex-col">
          <PipelineProgress
            specsApproved={hasApprovedSpec}
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
          />
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col">
            <TabsList className="mx-3 mt-1">
              <TabsTrigger value="specs">Specs</TabsTrigger>
              <TabsTrigger value="designs">Designs</TabsTrigger>
              <TabsTrigger value="decisions">
                Decisions{pendingDecisions.length > 0 ? ` (${pendingDecisions.length})` : ""}
              </TabsTrigger>
              <TabsTrigger value="tasks">Tasks</TabsTrigger>
              <TabsTrigger value="codes">Code</TabsTrigger>
              <TabsTrigger value="prs">PRs</TabsTrigger>
              <TabsTrigger value="voice">Voice</TabsTrigger>
              <TabsTrigger value="issues">Issues</TabsTrigger>
              <TabsTrigger value="audits">Audit</TabsTrigger>
              <TabsTrigger value="watches">Watch</TabsTrigger>
            </TabsList>
            <TabsContent value="specs" className="flex-1 overflow-hidden">
              <SpecPanel
                conversationId={conversationId}
                onSpecApproved={handleSpecApproved}
              />
            </TabsContent>
            <TabsContent value="designs" className="flex-1 overflow-hidden">
              <DesignPanel
                conversationId={conversationId}
                onDesignApproved={handleDesignApproved}
                preselectedSpecId={preselectedSpecId}
              />
            </TabsContent>
            <TabsContent value="decisions" className="flex-1 overflow-hidden">
              <DecisionPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="tasks" className="flex-1 overflow-hidden">
              <TaskPanel
                conversationId={conversationId}
                preselectedDesignId={preselectedDesignId}
                onTaskDone={handleTaskDone}
              />
            </TabsContent>
            <TabsContent value="codes" className="flex-1 overflow-hidden">
              <CodePanel
                conversationId={conversationId}
                preselectedTaskId={preselectedTaskId}
                onCodeApproved={handleCodeApproved}
              />
            </TabsContent>
            <TabsContent value="prs" className="flex-1 overflow-hidden">
              <PRPanel
                conversationId={conversationId}
                preselectedCodeId={preselectedCodeId}
              />
            </TabsContent>
            <TabsContent value="voice" className="flex-1 overflow-hidden">
              <VoicePanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="issues" className="flex-1 overflow-hidden">
              <IssuePanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="audits" className="flex-1 overflow-hidden">
              <AuditPanel conversationId={conversationId} />
            </TabsContent>
            <TabsContent value="watches" className="flex-1 overflow-hidden">
              <WatchPanel conversationId={conversationId} />
            </TabsContent>
          </Tabs>
        </aside>
      )}
    </div>
  );
}
