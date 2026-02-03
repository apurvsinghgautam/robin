"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, PanelRightClose, PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InvestigationChat } from "@/components/investigation/InvestigationChat";
import { ToolPanel } from "@/components/tools/ToolPanel";
import { useInvestigationStore } from "@/stores/investigationStore";

export default function InvestigationDetailPage() {
  const params = useParams();
  const investigationId = params.id as string;
  const [isToolPanelOpen, setIsToolPanelOpen] = useState(true);

  const {
    currentId,
    messages,
    isStreaming,
    currentResponse,
    activeTools,
    toolHistory,
    subagentResults,
    searchProgress,
    connectToStream,
    disconnect,
  } = useInvestigationStore();

  useEffect(() => {
    if (investigationId) {
      connectToStream(investigationId);
    }

    return () => {
      disconnect();
    };
  }, [investigationId, connectToStream, disconnect]);

  const isLoading = isStreaming && messages.length === 0 && !currentResponse;

  return (
    <div className="h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 border-b border-border px-4 py-3 flex items-center justify-between bg-card/50 backdrop-blur">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">Investigation</h1>
          <span className="text-xs text-muted-foreground font-mono bg-muted px-2 py-1 rounded">
            {investigationId}
          </span>
          {isStreaming && (
            <div className="flex items-center gap-2 text-sm text-primary">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Streaming...</span>
            </div>
          )}
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setIsToolPanelOpen(!isToolPanelOpen)}
          className="lg:hidden"
        >
          {isToolPanelOpen ? (
            <PanelRightClose className="h-5 w-5" />
          ) : (
            <PanelRight className="h-5 w-5" />
          )}
        </Button>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Section */}
        <div
          className={`flex-1 flex flex-col ${
            isToolPanelOpen ? "lg:pr-0" : ""
          }`}
        >
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-4">
                <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
                <div className="space-y-2">
                  <p className="text-lg font-medium">Starting investigation...</p>
                  <p className="text-sm text-muted-foreground">
                    Connecting to dark web intelligence sources
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <InvestigationChat
              messages={messages}
              currentResponse={currentResponse}
              isStreaming={isStreaming}
              investigationId={investigationId}
              searchProgress={searchProgress}
            />
          )}
        </div>

        {/* Tool Panel */}
        <div
          className={`
            ${isToolPanelOpen ? "w-80 lg:w-96" : "w-0"}
            transition-all duration-300 ease-in-out
            border-l border-border bg-card/30
            overflow-hidden flex-shrink-0
            absolute lg:relative right-0 top-0 h-full lg:h-auto
            z-10 lg:z-auto
          `}
        >
          {isToolPanelOpen && (
            <ToolPanel
              activeTools={activeTools}
              toolHistory={toolHistory}
              subagentResults={subagentResults}
              searchProgress={searchProgress}
              onClose={() => setIsToolPanelOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
