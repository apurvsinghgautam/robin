"use client";

import { useMemo } from "react";
import {
  Search,
  Globe,
  Users,
  FileText,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ToolExecution } from "@/types";

interface ToolTimelineProps {
  tools: ToolExecution[];
}

const TOOL_CONFIG: Record<
  string,
  {
    icon: typeof Search;
    label: string;
    color: string;
    bgColor: string;
    lineColor: string;
  }
> = {
  darkweb_search: {
    icon: Search,
    label: "Dark Web Search",
    color: "text-blue-400",
    bgColor: "bg-blue-500/20",
    lineColor: "bg-blue-500/50",
  },
  darkweb_scrape: {
    icon: Globe,
    label: "Dark Web Scrape",
    color: "text-green-400",
    bgColor: "bg-green-500/20",
    lineColor: "bg-green-500/50",
  },
  delegate_analysis: {
    icon: Users,
    label: "Delegate Analysis",
    color: "text-purple-400",
    bgColor: "bg-purple-500/20",
    lineColor: "bg-purple-500/50",
  },
  save_report: {
    icon: FileText,
    label: "Save Report",
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20",
    lineColor: "bg-yellow-500/50",
  },
};

const DEFAULT_TOOL_CONFIG = {
  icon: Search,
  label: "Tool",
  color: "text-gray-400",
  bgColor: "bg-gray-500/20",
  lineColor: "bg-gray-500/50",
};

interface TimelineItemProps {
  tool: ToolExecution;
  isLast: boolean;
}

function TimelineItem({ tool, isLast }: TimelineItemProps) {
  const config = TOOL_CONFIG[tool.tool] || {
    ...DEFAULT_TOOL_CONFIG,
    label: tool.tool,
  };
  const Icon = config.icon;

  const formattedDuration = useMemo(() => {
    if (!tool.duration_ms) return null;
    if (tool.duration_ms < 1000) return `${tool.duration_ms}ms`;
    return `${(tool.duration_ms / 1000).toFixed(1)}s`;
  }, [tool.duration_ms]);

  const formattedTime = useMemo(() => {
    const date = new Date(tool.started_at);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }, [tool.started_at]);

  const inputSummary = useMemo(() => {
    const input = tool.input;
    if (input.query) {
      const query = String(input.query);
      return query.length > 40 ? query.slice(0, 40) + "..." : query;
    }
    if (input.url) {
      const url = String(input.url);
      return url.length > 40 ? url.slice(0, 40) + "..." : url;
    }
    return null;
  }, [tool.input]);

  return (
    <div className="relative flex gap-3">
      {/* Timeline Line */}
      {!isLast && (
        <div
          className={cn(
            "absolute left-[15px] top-8 w-0.5 h-[calc(100%-8px)]",
            config.lineColor
          )}
        />
      )}

      {/* Icon */}
      <div
        className={cn(
          "relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          config.bgColor
        )}
      >
        <Icon className={cn("h-4 w-4", config.color)} />
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">{config.label}</span>
          <div className="flex items-center gap-2">
            {formattedDuration && (
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formattedDuration}
              </span>
            )}
            <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          </div>
        </div>

        {inputSummary && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {inputSummary}
          </p>
        )}

        <span className="text-xs text-muted-foreground/70 mt-1 block">
          {formattedTime}
        </span>
      </div>
    </div>
  );
}

export function ToolTimeline({ tools }: ToolTimelineProps) {
  // Sort tools by started_at in chronological order
  const sortedTools = useMemo(() => {
    return [...tools].sort(
      (a, b) =>
        new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    );
  }, [tools]);

  if (sortedTools.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-muted-foreground">No tool history</p>
      </div>
    );
  }

  return (
    <div className="space-y-0">
      {sortedTools.map((tool, index) => (
        <TimelineItem
          key={tool.id}
          tool={tool}
          isLast={index === sortedTools.length - 1}
        />
      ))}
    </div>
  );
}
