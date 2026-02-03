"use client";

import { useMemo } from "react";
import {
  Search,
  Globe,
  Users,
  FileText,
  Loader2,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import { ToolExecution } from "@/types";

interface ToolCardProps extends ToolExecution {}

const TOOL_CONFIG: Record<
  string,
  {
    icon: typeof Search;
    label: string;
    color: string;
    bgColor: string;
    borderColor: string;
  }
> = {
  darkweb_search: {
    icon: Search,
    label: "Dark Web Search",
    color: "text-blue-400",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
  },
  darkweb_scrape: {
    icon: Globe,
    label: "Dark Web Scrape",
    color: "text-green-400",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/30",
  },
  delegate_analysis: {
    icon: Users,
    label: "Delegate Analysis",
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/30",
  },
  save_report: {
    icon: FileText,
    label: "Save Report",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
  },
};

const DEFAULT_TOOL_CONFIG = {
  icon: Search,
  label: "Tool",
  color: "text-gray-400",
  bgColor: "bg-gray-500/10",
  borderColor: "border-gray-500/30",
};

export function ToolCard({
  id,
  tool,
  input,
  status,
  duration_ms,
  started_at,
}: ToolCardProps) {
  const config = TOOL_CONFIG[tool] || { ...DEFAULT_TOOL_CONFIG, label: tool };
  const Icon = config.icon;
  const isRunning = status === "running";

  const inputSummary = useMemo(() => {
    if (input.query) return `Query: "${input.query}"`;
    if (input.url) return `URL: ${input.url}`;
    if (input.targets) {
      const targets = input.targets as unknown[];
      return `${targets.length} target${targets.length !== 1 ? "s" : ""}`;
    }
    if (input.agent_type) return `Agent: ${input.agent_type}`;
    const keys = Object.keys(input);
    if (keys.length > 0) {
      return `${keys.length} parameter${keys.length !== 1 ? "s" : ""}`;
    }
    return null;
  }, [input]);

  const formattedDuration = useMemo(() => {
    if (!duration_ms) return null;
    if (duration_ms < 1000) return `${duration_ms}ms`;
    return `${(duration_ms / 1000).toFixed(1)}s`;
  }, [duration_ms]);

  return (
    <Card
      className={cn(
        "p-3 border transition-all",
        config.bgColor,
        config.borderColor,
        isRunning && "animate-pulse"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Left: Icon and Info */}
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <div
            className={cn(
              "flex-shrink-0 p-1.5 rounded-md",
              config.bgColor
            )}
          >
            <Icon className={cn("h-4 w-4", config.color)} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium truncate">
                {config.label}
              </span>
            </div>
            {inputSummary && (
              <p className="text-xs text-muted-foreground truncate mt-0.5">
                {inputSummary}
              </p>
            )}
          </div>
        </div>

        {/* Right: Status */}
        <div className="flex-shrink-0 flex items-center gap-2">
          {isRunning ? (
            <div className="flex items-center gap-1.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Running</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              {formattedDuration && (
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  <Clock className="h-3 w-3 mr-1" />
                  {formattedDuration}
                </Badge>
              )}
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
