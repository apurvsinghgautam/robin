"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";
import { ToolCard } from "./ToolCard";
import { ToolTimeline } from "./ToolTimeline";
import { SubAgentResults } from "./SubAgentResults";
import { SearchProgress } from "./SearchProgress";
import { ToolExecution, SubAgentResult, SearchProgress as SearchProgressType } from "@/types";
import { useState } from "react";

interface ToolPanelProps {
  activeTools: ToolExecution[];
  toolHistory: ToolExecution[];
  subagentResults: SubAgentResult[];
  searchProgress: SearchProgressType | null;
  onClose?: () => void;
}

export function ToolPanel({
  activeTools,
  toolHistory,
  subagentResults,
  searchProgress,
  onClose,
}: ToolPanelProps) {
  const [activeToolsOpen, setActiveToolsOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [subagentsOpen, setSubagentsOpen] = useState(true);

  const hasActiveTools = activeTools.length > 0;
  const hasHistory = toolHistory.length > 0;
  const hasSubagents = subagentResults.length > 0;
  const hasSearchProgress = searchProgress !== null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border px-4 py-3 flex items-center justify-between">
        <h2 className="font-semibold text-sm">Tool Activity</h2>
        {onClose && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-8 w-8 lg:hidden"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 px-4 py-4">
        <div className="space-y-4">
          {/* Search Progress Section */}
          {hasSearchProgress && (
            <SearchProgress progress={searchProgress} />
          )}

          {/* Active Tools Section */}
          {hasActiveTools && (
            <Collapsible open={activeToolsOpen} onOpenChange={setActiveToolsOpen}>
              <CollapsibleTrigger className="flex items-center justify-between w-full py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Active Tools</span>
                  <span className="text-xs bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full">
                    {activeTools.length}
                  </span>
                </div>
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform ${
                    activeToolsOpen ? "rotate-180" : ""
                  }`}
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {activeTools.map((tool) => (
                  <ToolCard key={tool.id} {...tool} />
                ))}
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Tool History Section */}
          {hasHistory && (
            <Collapsible open={historyOpen} onOpenChange={setHistoryOpen}>
              <CollapsibleTrigger className="flex items-center justify-between w-full py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Tool History</span>
                  <span className="text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded-full">
                    {toolHistory.length}
                  </span>
                </div>
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform ${
                    historyOpen ? "rotate-180" : ""
                  }`}
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-2">
                <ToolTimeline tools={toolHistory} />
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Sub-Agent Results Section */}
          {hasSubagents && (
            <Collapsible open={subagentsOpen} onOpenChange={setSubagentsOpen}>
              <CollapsibleTrigger className="flex items-center justify-between w-full py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Sub-Agent Analysis</span>
                  <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded-full">
                    {subagentResults.length}
                  </span>
                </div>
                <ChevronDown
                  className={`h-4 w-4 text-muted-foreground transition-transform ${
                    subagentsOpen ? "rotate-180" : ""
                  }`}
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="pt-2">
                <SubAgentResults results={subagentResults} />
              </CollapsibleContent>
            </Collapsible>
          )}

          {/* Empty State */}
          {!hasActiveTools && !hasHistory && !hasSubagents && !hasSearchProgress && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">
                No tool activity yet
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Tools will appear here as they execute
              </p>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
