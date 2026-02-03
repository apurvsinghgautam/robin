"use client";

import { useState } from "react";
import { Shield, Fingerprint, Bug, Store, ChevronDown, Loader2, XCircle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { Markdown } from "@/components/ui/markdown";

export type AgentType =
  | "ThreatActorProfiler"
  | "IOCExtractor"
  | "MalwareAnalyst"
  | "MarketplaceInvestigator";

export type AgentStatus = "running" | "completed" | "failed";

export interface SubAgentBadgeProps {
  agentType: AgentType;
  status: AgentStatus;
  analysis?: string;
}

const AGENT_CONFIG: Record<
  AgentType,
  {
    icon: typeof Shield;
    label: string;
    color: string;
    bgColor: string;
    borderColor: string;
  }
> = {
  ThreatActorProfiler: {
    icon: Shield,
    label: "Threat Actor Profiler",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
  },
  IOCExtractor: {
    icon: Fingerprint,
    label: "IOC Extractor",
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30",
  },
  MalwareAnalyst: {
    icon: Bug,
    label: "Malware Analyst",
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
  },
  MarketplaceInvestigator: {
    icon: Store,
    label: "Marketplace Investigator",
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
  },
};

function StatusIndicator({ status }: { status: AgentStatus }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />;
    case "completed":
      return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
    case "failed":
      return <XCircle className="h-3.5 w-3.5 text-red-500" />;
  }
}

export function SubAgentBadge({
  agentType,
  status,
  analysis,
}: SubAgentBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const config = AGENT_CONFIG[agentType];
  const Icon = config.icon;
  const hasAnalysis = analysis && analysis.trim().length > 0;

  // Non-expandable version for running/failed without analysis
  if (!hasAnalysis) {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-2 px-3 py-2 rounded-lg border",
          config.bgColor,
          config.borderColor
        )}
      >
        <Icon className={cn("h-4 w-4", config.color)} />
        <span className="text-sm font-medium">{config.label}</span>
        <StatusIndicator status={status} />
      </div>
    );
  }

  // Expandable version with analysis
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger
        className={cn(
          "w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border transition-colors",
          config.bgColor,
          config.borderColor,
          "hover:opacity-90"
        )}
      >
        <div className="flex items-center gap-2">
          <Icon className={cn("h-4 w-4", config.color)} />
          <span className="text-sm font-medium">{config.label}</span>
          <StatusIndicator status={status} />
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div
          className={cn(
            "mt-1 px-3 py-3 rounded-b-lg border border-t-0",
            config.bgColor,
            config.borderColor
          )}
        >
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Markdown content={analysis} />
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
