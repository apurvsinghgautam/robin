"use client";

import { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "./MessageBubble";
import { StreamingResponse } from "./StreamingResponse";
import { QueryInput } from "./QueryInput";
import { SearchProgress } from "@/components/tools/SearchProgress";
import { useInvestigationStore } from "@/stores/investigationStore";
import { Message, SearchProgress as SearchProgressType } from "@/types";

interface InvestigationChatProps {
  messages: Message[];
  currentResponse: string;
  isStreaming: boolean;
  investigationId: string;
  searchProgress?: SearchProgressType | null;
}

export function InvestigationChat({
  messages,
  currentResponse,
  isStreaming,
  investigationId,
  searchProgress,
}: InvestigationChatProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { sendFollowUp } = useInvestigationStore();

  // Auto-scroll to bottom on new content
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, currentResponse, searchProgress]);

  const handleSendFollowUp = async (query: string) => {
    await sendFollowUp(query);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages Area */}
      <ScrollArea className="flex-1 px-4 py-6" ref={scrollAreaRef}>
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((message, index) => (
            <MessageBubble
              key={message.id || index}
              role={message.role}
              content={message.content}
              timestamp={new Date(message.created_at)}
            />
          ))}

          {/* Search progress indicator - shown in main chat when searching */}
          {searchProgress && searchProgress.status !== 'complete' && (
            <div className="max-w-md">
              <SearchProgress progress={searchProgress} />
            </div>
          )}

          {/* Current streaming response */}
          {currentResponse && (
            <StreamingResponse
              content={currentResponse}
              isStreaming={isStreaming}
            />
          )}

          {/* Scroll anchor */}
          <div ref={bottomRef} />
        </div>
      </ScrollArea>

      {/* Input Area */}
      <div className="flex-shrink-0 border-t border-border p-4 bg-background/50 backdrop-blur">
        <div className="max-w-3xl mx-auto">
          <QueryInput
            onSubmit={handleSendFollowUp}
            isLoading={isStreaming}
            placeholder="Ask a follow-up question..."
          />
        </div>
      </div>
    </div>
  );
}
