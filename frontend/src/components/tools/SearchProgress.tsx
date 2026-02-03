"use client";

import { Search, CheckCircle, XCircle, Clock, AlertCircle } from "lucide-react";
import { SearchProgress as SearchProgressType } from "@/types";

interface SearchProgressProps {
  progress: SearchProgressType;
}

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bgColor: string }> = {
  starting: {
    icon: <Clock className="h-3 w-3" />,
    color: "text-blue-400",
    bgColor: "bg-blue-500/20",
  },
  searching: {
    icon: <Search className="h-3 w-3 animate-pulse" />,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20",
  },
  success: {
    icon: <CheckCircle className="h-3 w-3" />,
    color: "text-green-400",
    bgColor: "bg-green-500/20",
  },
  failed: {
    icon: <XCircle className="h-3 w-3" />,
    color: "text-red-400",
    bgColor: "bg-red-500/20",
  },
  timeout: {
    icon: <Clock className="h-3 w-3" />,
    color: "text-orange-400",
    bgColor: "bg-orange-500/20",
  },
  complete: {
    icon: <CheckCircle className="h-3 w-3" />,
    color: "text-green-400",
    bgColor: "bg-green-500/20",
  },
  early_exit: {
    icon: <AlertCircle className="h-3 w-3" />,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/20",
  },
  high_failure_rate: {
    icon: <AlertCircle className="h-3 w-3" />,
    color: "text-orange-400",
    bgColor: "bg-orange-500/20",
  },
};

export function SearchProgress({ progress }: SearchProgressProps) {
  const config = statusConfig[progress.status] || statusConfig.searching;
  const progressPercent = progress.total_engines > 0
    ? Math.round((progress.completed_engines / progress.total_engines) * 100)
    : 0;

  return (
    <div className="rounded-lg border border-border bg-card/50 p-3 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className={`p-1.5 rounded ${config.bgColor}`}>
          <Search className={`h-4 w-4 ${config.color}`} />
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium">Dark Web Search</div>
          <div className="text-xs text-muted-foreground">{progress.message}</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300 ease-out rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{progress.completed_engines} / {progress.total_engines} engines</span>
          <span>{progress.total_results} results</span>
        </div>
      </div>

      {/* Current Engine Status */}
      {progress.engine_name && progress.status !== 'complete' && (
        <div className={`flex items-center gap-2 text-xs ${config.color}`}>
          {config.icon}
          <span className="truncate">{progress.engine_name}</span>
        </div>
      )}
    </div>
  );
}
