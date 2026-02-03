"use client";

import { Bot } from "lucide-react";
import { Markdown } from "@/components/ui/markdown";

interface StreamingResponseProps {
  content: string;
  isStreaming?: boolean;
}

export function StreamingResponse({
  content,
  isStreaming = true,
}: StreamingResponseProps) {
  if (!content) return null;

  return (
    <div className="flex gap-3">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-muted text-muted-foreground">
        <Bot className="h-4 w-4" />
      </div>

      {/* Content */}
      <div className="flex flex-col items-start max-w-[85%]">
        <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-muted text-foreground">
          <Markdown content={content} />
          {isStreaming && (
            <span className="inline-block w-2 h-5 ml-0.5 bg-primary rounded-sm animate-blink" />
          )}
        </div>

        {isStreaming && (
          <span className="text-xs text-muted-foreground mt-1.5 px-1 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-primary rounded-full animate-pulse" />
            Generating response...
          </span>
        )}
      </div>
    </div>
  );
}
