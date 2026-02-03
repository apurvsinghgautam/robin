'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import type { SSEEvent, SSEToolStartEvent, SSEToolEndEvent, SSESubagentStartEvent, SSESubagentEndEvent, SSECompleteEvent, SSEErrorEvent } from '@/types';
import { investigationAPI } from '@/lib/api';

// ============================================
// Types
// ============================================

interface UseSSEOptions {
  onText?: (content: string) => void;
  onToolStart?: (data: SSEToolStartEvent['data']) => void;
  onToolEnd?: (data: SSEToolEndEvent['data']) => void;
  onSubagentStart?: (data: SSESubagentStartEvent['data']) => void;
  onSubagentEnd?: (data: SSESubagentEndEvent['data']) => void;
  onComplete?: (data: SSECompleteEvent['data']) => void;
  onError?: (data: SSEErrorEvent['data']) => void;
  autoReconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectDelay?: number;
}

interface UseSSEReturn {
  isConnected: boolean;
  isConnecting: boolean;
  events: SSEEvent[];
  error: Error | null;
  connect: (investigationId: string) => void;
  disconnect: () => void;
  clearEvents: () => void;
}

// ============================================
// Hook Implementation
// ============================================

export function useSSE(options: UseSSEOptions = {}): UseSSEReturn {
  const {
    onText,
    onToolStart,
    onToolEnd,
    onSubagentStart,
    onSubagentEnd,
    onComplete,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 3,
    reconnectDelay = 1000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentInvestigationIdRef = useRef<string | null>(null);

  // Clear reconnect timeout on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const handleEvent = useCallback(
    (event: SSEEvent) => {
      setEvents((prev) => [...prev, event]);

      switch (event.type) {
        case 'text':
          onText?.(event.data.content);
          break;
        case 'tool_start':
          onToolStart?.(event.data);
          break;
        case 'tool_end':
          onToolEnd?.(event.data);
          break;
        case 'subagent_start':
          onSubagentStart?.(event.data);
          break;
        case 'subagent_end':
          onSubagentEnd?.(event.data);
          break;
        case 'complete':
          onComplete?.(event.data);
          // Reset reconnect attempts on successful completion
          reconnectAttemptsRef.current = 0;
          break;
        case 'error':
          onError?.(event.data);
          setError(new Error(event.data.message));
          break;
      }
    },
    [onText, onToolStart, onToolEnd, onSubagentStart, onSubagentEnd, onComplete, onError]
  );

  const connect = useCallback(
    (investigationId: string) => {
      // Close existing connection if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      setIsConnecting(true);
      setError(null);
      currentInvestigationIdRef.current = investigationId;

      const url = investigationAPI.getStreamUrl(investigationId);
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.onmessage = (messageEvent) => {
        try {
          const event: SSEEvent = JSON.parse(messageEvent.data);
          handleEvent(event);

          // Close connection on complete or error
          if (event.type === 'complete' || event.type === 'error') {
            eventSource.close();
            setIsConnected(false);
          }
        } catch (parseError) {
          console.error('Failed to parse SSE event:', parseError);
        }
      };

      eventSource.onerror = (errorEvent) => {
        console.error('SSE connection error:', errorEvent);
        setIsConnected(false);
        setIsConnecting(false);
        eventSource.close();

        // Attempt reconnection
        if (
          autoReconnect &&
          reconnectAttemptsRef.current < maxReconnectAttempts &&
          currentInvestigationIdRef.current
        ) {
          reconnectAttemptsRef.current += 1;
          const delay = reconnectDelay * Math.pow(2, reconnectAttemptsRef.current - 1);

          reconnectTimeoutRef.current = setTimeout(() => {
            if (currentInvestigationIdRef.current) {
              connect(currentInvestigationIdRef.current);
            }
          }, delay);
        } else {
          setError(new Error('SSE connection failed after max reconnect attempts'));
        }
      };
    },
    [autoReconnect, maxReconnectAttempts, reconnectDelay, handleEvent]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
    currentInvestigationIdRef.current = null;
    reconnectAttemptsRef.current = 0;
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return {
    isConnected,
    isConnecting,
    events,
    error,
    connect,
    disconnect,
    clearEvents,
  };
}

// ============================================
// Utility hook for simplified text streaming
// ============================================

export function useSSEText(investigationId: string | null) {
  const [text, setText] = useState('');
  const [isComplete, setIsComplete] = useState(false);

  const { isConnected, isConnecting, error, connect, disconnect } = useSSE({
    onText: (content) => {
      setText((prev) => prev + content);
    },
    onComplete: () => {
      setIsComplete(true);
    },
  });

  useEffect(() => {
    if (investigationId) {
      setText('');
      setIsComplete(false);
      connect(investigationId);
    }

    return () => {
      disconnect();
    };
  }, [investigationId, connect, disconnect]);

  return {
    text,
    isStreaming: isConnected && !isComplete,
    isConnecting,
    isComplete,
    error,
  };
}

export default useSSE;
