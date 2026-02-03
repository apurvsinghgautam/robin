"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface QueryInputProps {
  onSubmit: (query: string) => void | Promise<void>;
  isLoading?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
}

export function QueryInput({
  onSubmit,
  isLoading = false,
  placeholder = "Enter your query...",
  autoFocus = false,
}: QueryInputProps) {
  const [query, setQuery] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [query]);

  // Auto-focus on mount if specified
  useEffect(() => {
    if (autoFocus && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [autoFocus]);

  const handleSubmit = async () => {
    if (!query.trim() || isLoading) return;

    const submittedQuery = query.trim();
    setQuery("");
    await onSubmit(submittedQuery);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Cmd/Ctrl + Enter
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
      return;
    }

    // Submit on Enter (without Shift for newline)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="relative flex items-end gap-2">
      <div className="flex-1 relative">
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          rows={1}
          className="w-full min-h-[44px] max-h-[200px] px-4 py-3 pr-12 bg-muted/50 border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <div className="absolute right-1 bottom-1">
          <Button
            size="icon"
            onClick={handleSubmit}
            disabled={!query.trim() || isLoading}
            className="h-9 w-9"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
      <div className="hidden sm:block text-xs text-muted-foreground pb-3">
        <kbd className="px-1 py-0.5 bg-muted rounded text-xs">Enter</kbd> to send
      </div>
    </div>
  );
}
