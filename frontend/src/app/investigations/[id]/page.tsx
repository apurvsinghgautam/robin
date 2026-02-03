'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Send,
  Loader2,
  AlertCircle,
  Network,
  FileText,
  Clock,
  Wrench,
  Bot,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Markdown } from '@/components/ui/markdown';
import { useInvestigationStore } from '@/stores/investigationStore';
import { formatDuration } from '@/lib/utils';
import type { Message, ToolExecution, SubAgentResult } from '@/types';

// ============================================
// Investigation Detail Page
// ============================================

export default function InvestigationPage() {
  const params = useParams();
  const router = useRouter();
  const investigationId = params.id as string;

  const [followUpQuery, setFollowUpQuery] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    currentId,
    messages,
    isStreaming,
    currentResponse,
    activeTools,
    toolHistory,
    subagentResults,
    error,
    loadInvestigation,
    sendFollowUp,
    connectToStream,
  } = useInvestigationStore();

  // Load investigation on mount
  useEffect(() => {
    if (investigationId && investigationId !== currentId) {
      loadInvestigation(investigationId).catch(console.error);
    }
  }, [investigationId, currentId, loadInvestigation]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentResponse]);

  const handleFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!followUpQuery.trim() || isStreaming) return;

    try {
      await sendFollowUp(followUpQuery.trim());
      setFollowUpQuery('');
    } catch (err) {
      console.error('Failed to send follow-up:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="flex items-center justify-between p-4 border-b border-border bg-card/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <Link href="/investigations">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="font-semibold">Investigation</h1>
            <p className="text-xs text-muted-foreground font-mono">
              {investigationId}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/graph?investigation=${investigationId}`}>
            <Button variant="outline" size="sm">
              <Network className="h-4 w-4 mr-2" />
              View Graph
            </Button>
          </Link>
          <Link href={`/reports/new?investigation=${investigationId}`}>
            <Button variant="outline" size="sm">
              <FileText className="h-4 w-4 mr-2" />
              Create Report
            </Button>
          </Link>
        </div>
      </header>

      {/* Messages Area */}
      <ScrollArea className="flex-1 p-4">
        <div className="max-w-6xl mx-auto space-y-6">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Active Tools */}
          {activeTools.length > 0 && (
            <div className="space-y-2">
              {activeTools.map((tool) => (
                <ToolIndicator key={tool.id} tool={tool} />
              ))}
            </div>
          )}

          {/* Subagent Results */}
          {subagentResults.length > 0 && (
            <div className="space-y-2">
              {subagentResults.map((result, index) => (
                <SubAgentIndicator key={index} result={result} />
              ))}
            </div>
          )}

          {/* Streaming Response */}
          {currentResponse && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <Card className="flex-1">
                <CardContent className="p-4">
                  <Markdown content={currentResponse} />
                  {isStreaming && (
                    <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse" />
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Error State */}
          {error && (
            <Card className="border-destructive">
              <CardContent className="p-4 flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-destructive" />
                <div>
                  <p className="font-medium text-destructive">Error</p>
                  <p className="text-sm text-muted-foreground">{error.message}</p>
                </div>
              </CardContent>
            </Card>
          )}

          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Follow-up Input */}
      <div className="p-4 border-t border-border bg-card/50 backdrop-blur-sm">
        <form onSubmit={handleFollowUp} className="max-w-6xl mx-auto flex gap-2">
          <Input
            placeholder="Ask a follow-up question..."
            value={followUpQuery}
            onChange={(e) => setFollowUpQuery(e.target.value)}
            disabled={isStreaming}
            className="flex-1"
          />
          <Button type="submit" disabled={!followUpQuery.trim() || isStreaming}>
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );
}

// ============================================
// Message Bubble Component
// ============================================

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'bg-primary' : 'bg-primary/10'
        }`}
      >
        {isUser ? (
          <span className="text-sm font-medium text-primary-foreground">U</span>
        ) : (
          <Bot className="h-4 w-4 text-primary" />
        )}
      </div>
      <Card className={`flex-1 ${isUser ? 'bg-primary text-primary-foreground max-w-[80%]' : ''}`}>
        <CardContent className="p-4">
          {isUser ? (
            <p className="text-sm">{message.content}</p>
          ) : (
            <Markdown content={message.content} />
          )}
          {message.tool_executions && message.tool_executions.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50">
              <p className="text-xs text-muted-foreground mb-2">Tools used:</p>
              <div className="flex flex-wrap gap-1">
                {message.tool_executions.map((tool) => (
                  <Badge key={tool.id} variant="secondary" className="text-xs">
                    {tool.tool}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================
// Tool Indicator Component
// ============================================

function ToolIndicator({ tool }: { tool: ToolExecution }) {
  return (
    <div className="tool-indicator tool-indicator-active">
      <Wrench className="h-4 w-4 text-primary animate-spin" />
      <span className="flex-1">Running: {tool.tool}</span>
      <Badge variant="secondary" className="text-xs">
        <Clock className="h-3 w-3 mr-1" />
        In progress
      </Badge>
    </div>
  );
}

// ============================================
// SubAgent Indicator Component
// ============================================

function SubAgentIndicator({ result }: { result: SubAgentResult }) {
  const isComplete = !!result.completed_at;

  return (
    <div
      className={`tool-indicator ${
        isComplete
          ? result.success
            ? 'tool-indicator-complete'
            : 'tool-indicator-error'
          : 'tool-indicator-active'
      }`}
    >
      {isComplete ? (
        result.success ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        ) : (
          <XCircle className="h-4 w-4 text-destructive" />
        )
      ) : (
        <Bot className="h-4 w-4 text-primary animate-pulse" />
      )}
      <span className="flex-1">
        {isComplete ? 'Completed' : 'Running'}: {result.agent_type}
      </span>
      {result.duration_ms && (
        <Badge variant="secondary" className="text-xs">
          {formatDuration(result.duration_ms)}
        </Badge>
      )}
    </div>
  );
}
