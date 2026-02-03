"use client";

import { useMemo } from "react";
import { User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import { Markdown } from "@/components/ui/markdown";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  timestamp?: Date;
}

export function MessageBubble({
  role,
  content,
  isStreaming = false,
  timestamp,
}: MessageBubbleProps) {
  const isUser = role === "user";

  const formattedTime = useMemo(() => {
    if (!timestamp) return null;
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit"
    });
  }, [timestamp]);

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
      </div>

      {/* Message Content */}
      <div
        className={cn(
          "flex flex-col max-w-[85%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "px-4 py-3 rounded-2xl",
            isUser
              ? "bg-primary text-primary-foreground rounded-br-md"
              : "bg-muted text-foreground rounded-bl-md"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap break-words text-sm">{content}</p>
          ) : (
            <div>
              <Markdown content={content} />
              {isStreaming && (
                <span className="inline-block w-2 h-5 ml-0.5 bg-primary rounded-sm animate-blink" />
              )}
            </div>
          )}
        </div>

        {/* Timestamp */}
        {formattedTime && (
          <span className="text-xs text-muted-foreground mt-1 px-1">
            {formattedTime}
          </span>
        )}
      </div>
    </div>
  );
}
