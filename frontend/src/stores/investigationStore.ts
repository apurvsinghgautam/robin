import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import type {
  Message,
  ToolExecution,
  SubAgentResult,
  SSECompleteEvent,
  SearchProgress,
} from '@/types';
import { investigationAPI } from '@/lib/api';

// ============================================
// Types
// ============================================

interface InvestigationState {
  // Current investigation state
  currentId: string | null;
  messages: Message[];
  isStreaming: boolean;
  currentResponse: string;
  activeTools: ToolExecution[];
  toolHistory: ToolExecution[];
  subagentResults: SubAgentResult[];
  searchProgress: SearchProgress | null;
  error: Error | null;

  // SSE connection (for internal use)
  eventSource: EventSource | null;

  // Session info
  sessionId: string | null;
  totalDuration: number | null;
}

interface InvestigationActions {
  // Investigation actions
  startInvestigation: (query: string) => Promise<string>;
  sendFollowUp: (query: string) => Promise<string>;
  loadInvestigation: (id: string) => Promise<void>;
  connectToStream: (investigationId: string) => void;
  disconnect: () => void;

  // Streaming actions (called by SSE hook)
  appendText: (text: string) => void;
  addToolStart: (tool: ToolExecution) => void;
  updateToolEnd: (id: string, duration: number, output?: Record<string, unknown>, error?: string) => void;
  addSubAgentStart: (agentType: string) => void;
  addSubAgentResult: (result: SubAgentResult) => void;
  updateSearchProgress: (progress: SearchProgress) => void;
  completeInvestigation: (result: SSECompleteEvent['data']) => void;
  setError: (error: Error) => void;

  // State management
  setStreaming: (isStreaming: boolean) => void;
  reset: () => void;
  clearMessages: () => void;
}

export type InvestigationStore = InvestigationState & InvestigationActions;

// ============================================
// Initial State
// ============================================

const initialState: InvestigationState = {
  currentId: null,
  messages: [],
  isStreaming: false,
  currentResponse: '',
  activeTools: [],
  toolHistory: [],
  subagentResults: [],
  searchProgress: null,
  error: null,
  eventSource: null,
  sessionId: null,
  totalDuration: null,
};

// ============================================
// Store Implementation
// ============================================

export const useInvestigationStore = create<InvestigationStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        // Start a new investigation
        startInvestigation: async (query: string): Promise<string> => {
          // Disconnect any existing stream
          const { eventSource } = get();
          if (eventSource) {
            eventSource.close();
          }

          set({
            ...initialState,
            isStreaming: true,
            messages: [
              {
                id: `user-${Date.now()}`,
                role: 'user',
                content: query,
                created_at: new Date().toISOString(),
              },
            ],
          });

          try {
            const response = await investigationAPI.start({ query });
            set({ currentId: response.id });

            // Auto-connect to stream
            get().connectToStream(response.id);

            return response.id;
          } catch (error) {
            set({
              isStreaming: false,
              error: error instanceof Error ? error : new Error('Failed to start investigation'),
            });
            throw error;
          }
        },

        // Send a follow-up query
        sendFollowUp: async (query: string): Promise<string> => {
          const { currentId, messages, eventSource } = get();

          if (!currentId) {
            throw new Error('No active investigation');
          }

          // Disconnect existing stream
          if (eventSource) {
            eventSource.close();
          }

          // Add user message
          const userMessage: Message = {
            id: `user-${Date.now()}`,
            role: 'user',
            content: query,
            created_at: new Date().toISOString(),
          };

          set({
            messages: [...messages, userMessage],
            isStreaming: true,
            currentResponse: '',
            activeTools: [],
            subagentResults: [],
            error: null,
          });

          try {
            const response = await investigationAPI.followUp(currentId, { query });

            // Connect to new stream
            get().connectToStream(currentId);

            return response.id;
          } catch (error) {
            set({
              isStreaming: false,
              error: error instanceof Error ? error : new Error('Failed to send follow-up'),
            });
            throw error;
          }
        },

        // Load an existing investigation
        loadInvestigation: async (id: string): Promise<void> => {
          try {
            const details = await investigationAPI.get(id);

            // Construct messages from API response
            const messages: Message[] = [];

            // Add user message from initial query
            if (details.initial_query) {
              messages.push({
                id: `user-${details.created_at}`,
                role: 'user',
                content: details.initial_query,
                created_at: details.created_at,
              });
            }

            // Add assistant message from full response
            if (details.full_response) {
              messages.push({
                id: `assistant-${details.completed_at || details.created_at}`,
                role: 'assistant',
                content: details.full_response,
                created_at: details.completed_at || details.created_at,
                tool_executions: details.tools_used || [],
                subagent_results: details.subagent_results || [],
              });
            }

            set({
              currentId: id,
              messages,
              toolHistory: details.tools_used || [],
              subagentResults: details.subagent_results || [],
              isStreaming: details.status === 'running',
              currentResponse: '',
              activeTools: [],
              error: null,
            });

            // If still running, connect to stream
            if (details.status === 'running' || details.status === 'pending') {
              get().connectToStream(id);
            }
          } catch (error) {
            set({
              error: error instanceof Error ? error : new Error('Failed to load investigation'),
            });
            throw error;
          }
        },

        // Connect to SSE stream
        connectToStream: (investigationId: string) => {
          const { eventSource: existingSource } = get();

          // Disconnect existing connection if any
          if (existingSource) {
            existingSource.close();
          }

          const url = investigationAPI.getStreamUrl(investigationId);
          const eventSource = new EventSource(url);

          set({ eventSource, isStreaming: true, currentId: investigationId });

          // Handle incoming events
          eventSource.onmessage = (event) => {
            try {
              const data = JSON.parse(event.data);
              const state = get();

              // Debug: log all SSE events
              console.log('[SSE Event]', data.type, data.data);

              switch (data.type) {
                case 'text':
                  state.appendText(data.data.content);
                  break;

                case 'tool_start':
                  state.addToolStart({
                    id: data.data.id,
                    tool: data.data.tool,
                    input: data.data.input || {},
                    status: 'running',
                    started_at: new Date().toISOString(),
                  });
                  break;

                case 'tool_end':
                  state.updateToolEnd(
                    data.data.id,
                    data.data.duration_ms,
                    data.data.output,
                    data.data.error
                  );
                  break;

                case 'subagent_start':
                  state.addSubAgentStart(data.data.agent_type);
                  break;

                case 'subagent_end':
                  state.addSubAgentResult({
                    agent_type: data.data.agent_type,
                    analysis: data.data.analysis,
                    success: data.data.success,
                    started_at: new Date().toISOString(),
                    completed_at: new Date().toISOString(),
                    duration_ms: data.data.duration_ms,
                  });
                  break;

                case 'search_progress':
                  state.updateSearchProgress({
                    engine_name: data.data.engine_name,
                    status: data.data.status,
                    results_count: data.data.results_count,
                    total_engines: data.data.total_engines,
                    completed_engines: data.data.completed_engines,
                    total_results: data.data.total_results,
                    message: data.data.message,
                  });
                  break;

                case 'complete':
                  state.completeInvestigation(data.data);
                  eventSource.close();
                  break;

                case 'error':
                  state.setError(new Error(data.data.message));
                  eventSource.close();
                  break;
              }
            } catch (error) {
              console.error('Failed to parse SSE message:', error);
            }
          };

          eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            set({ isStreaming: false });
            eventSource.close();
          };
        },

        // Disconnect from SSE stream
        disconnect: () => {
          const { eventSource } = get();
          if (eventSource) {
            eventSource.close();
          }
          set({ eventSource: null, isStreaming: false });
        },

        // Append streaming text
        appendText: (text: string) => {
          set((state) => ({
            currentResponse: state.currentResponse + text,
          }));
        },

        // Add tool execution start
        addToolStart: (tool: ToolExecution) => {
          set((state) => ({
            activeTools: [...state.activeTools, tool],
          }));
        },

        // Update tool execution end
        updateToolEnd: (id: string, duration: number, output?: Record<string, unknown>, error?: string) => {
          set((state) => {
            const tool = state.activeTools.find((t) => t.id === id);
            if (!tool) return state;

            const updatedTool: ToolExecution = {
              ...tool,
              status: error ? 'error' : 'completed',
              duration_ms: duration,
              completed_at: new Date().toISOString(),
              output,
              error,
            };

            return {
              activeTools: state.activeTools.filter((t) => t.id !== id),
              toolHistory: [...state.toolHistory, updatedTool],
            };
          });
        },

        // Add subagent start
        addSubAgentStart: (agentType: string) => {
          const result: SubAgentResult = {
            agent_type: agentType,
            analysis: '',
            success: false,
            started_at: new Date().toISOString(),
          };
          set((state) => ({
            subagentResults: [...state.subagentResults, result],
          }));
        },

        // Add subagent result
        addSubAgentResult: (result: SubAgentResult) => {
          set((state) => {
            // Update existing or add new
            const existingIndex = state.subagentResults.findIndex(
              (r) => r.agent_type === result.agent_type && !r.completed_at
            );

            if (existingIndex >= 0) {
              const updated = [...state.subagentResults];
              updated[existingIndex] = {
                ...updated[existingIndex],
                ...result,
                completed_at: new Date().toISOString(),
              };
              return { subagentResults: updated };
            }

            return {
              subagentResults: [...state.subagentResults, result],
            };
          });
        },

        // Update search progress
        updateSearchProgress: (progress: SearchProgress) => {
          set({ searchProgress: progress });
        },

        // Complete the investigation
        completeInvestigation: (result: SSECompleteEvent['data']) => {
          const { messages, currentResponse, toolHistory, subagentResults } = get();

          // Create assistant message from current response
          const assistantMessage: Message = {
            id: `assistant-${Date.now()}`,
            role: 'assistant',
            content: result.text || currentResponse,
            created_at: new Date().toISOString(),
            tool_executions: toolHistory,
            subagent_results: subagentResults,
          };

          set({
            messages: [...messages, assistantMessage],
            isStreaming: false,
            currentResponse: '',
            activeTools: [],
            searchProgress: null,
            sessionId: result.session_id,
            totalDuration: result.duration_ms,
            error: null,
            eventSource: null,
          });
        },

        // Set error
        setError: (error: Error) => {
          set({
            isStreaming: false,
            error,
            searchProgress: null,
            eventSource: null,
          });
        },

        // Set streaming state
        setStreaming: (isStreaming: boolean) => {
          set({ isStreaming });
        },

        // Reset to initial state
        reset: () => {
          const { eventSource } = get();
          if (eventSource) {
            eventSource.close();
          }
          set(initialState);
        },

        // Clear messages only
        clearMessages: () => {
          set({
            messages: [],
            currentResponse: '',
            activeTools: [],
            toolHistory: [],
            subagentResults: [],
          });
        },
      }),
      {
        name: 'robin-investigation-store',
        partialize: (state) => ({
          currentId: state.currentId,
          messages: state.messages,
        }),
      }
    ),
    { name: 'InvestigationStore' }
  )
);

// ============================================
// Selectors
// ============================================

export const selectCurrentId = (state: InvestigationStore) => state.currentId;
export const selectMessages = (state: InvestigationStore) => state.messages;
export const selectIsStreaming = (state: InvestigationStore) => state.isStreaming;
export const selectCurrentResponse = (state: InvestigationStore) => state.currentResponse;
export const selectActiveTools = (state: InvestigationStore) => state.activeTools;
export const selectToolHistory = (state: InvestigationStore) => state.toolHistory;
export const selectSubagentResults = (state: InvestigationStore) => state.subagentResults;
export const selectError = (state: InvestigationStore) => state.error;
export const selectSearchProgress = (state: InvestigationStore) => state.searchProgress;

export default useInvestigationStore;
