// ============================================
// Core Investigation Types
// ============================================

export interface Investigation {
  id: string;
  query: string;
  status: 'pending' | 'streaming' | 'completed' | 'error';
  created_at: string;
  updated_at: string;
}

export interface InvestigationSummary {
  id: string;
  initial_query: string;
  query?: string; // Alias for backwards compatibility
  status: 'pending' | 'streaming' | 'completed' | 'error' | 'running' | 'failed';
  created_at: string;
  completed_at?: string;
  entity_count?: number;
  duration_ms?: number;
  model?: string;
  num_turns?: number;
}

export interface InvestigationDetail {
  id: string;
  session_id: string | null;
  initial_query: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  full_response: string | null;
  tools_used: ToolExecution[];
  subagent_results: SubAgentResult[];
  model: string;
  num_turns: number | null;
  duration_ms: number | null;
  created_at: string;
  completed_at: string | null;
}

// ============================================
// Message Types
// ============================================

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  tool_executions?: ToolExecution[];
  subagent_results?: SubAgentResult[];
}

export interface ToolExecution {
  id: string;
  tool: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: 'running' | 'completed' | 'error';
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  error?: string;
}

export interface SubAgentResult {
  agent_type: string;
  analysis: string;
  success: boolean;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

// ============================================
// Entity Types
// ============================================

export type EntityType =
  | 'threat_actor'
  | 'ioc'
  | 'malware'
  | 'marketplace'
  | 'vulnerability'
  | 'infrastructure'
  | 'person'
  | 'organization'
  | 'crypto_wallet'
  | 'domain'
  | 'ip_address'
  | 'email'
  | 'unknown';

export interface Entity {
  id: string;
  name: string;
  type: EntityType;
  description?: string;
  attributes: Record<string, unknown>;
  source?: string;
  confidence?: number;
  first_seen?: string;
  last_seen?: string;
}

// ============================================
// Graph Types
// ============================================

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  data: Entity;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  relationship_type: string;
  weight?: number;
  data?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphFilters {
  types: EntityType[];
  minConfidence?: number;
  searchQuery?: string;
}

// ============================================
// Report Types
// ============================================

export interface Report {
  id: string;
  title: string;
  investigation_id: string;
  sections: ReportSection[];
  created_at: string;
  updated_at: string;
  status: 'draft' | 'published';
}

export interface ReportSection {
  id: string;
  title: string;
  content: string;
  order: number;
  type: 'summary' | 'findings' | 'entities' | 'timeline' | 'recommendations' | 'custom';
}

export interface ReportExportOptions {
  format: 'md' | 'pdf' | 'html';
  includeGraph?: boolean;
  includeTimeline?: boolean;
}

// ============================================
// SSE Event Types
// ============================================

export interface SSETextEvent {
  type: 'text';
  data: {
    content: string;
  };
}

export interface SSEToolStartEvent {
  type: 'tool_start';
  data: {
    id: string;
    tool: string;
    input: Record<string, unknown>;
  };
}

export interface SSEToolEndEvent {
  type: 'tool_end';
  data: {
    id: string;
    tool: string;
    duration_ms: number;
    output?: Record<string, unknown>;
    error?: string;
  };
}

export interface SSESubagentStartEvent {
  type: 'subagent_start';
  data: {
    agent_type: string;
  };
}

export interface SSESubagentEndEvent {
  type: 'subagent_end';
  data: {
    agent_type: string;
    analysis: string;
    success: boolean;
    duration_ms?: number;
  };
}

export interface SSESearchProgressEvent {
  type: 'search_progress';
  data: {
    engine_name: string;
    status: 'starting' | 'searching' | 'success' | 'failed' | 'timeout' | 'complete' | 'early_exit' | 'high_failure_rate';
    results_count: number;
    total_engines: number;
    completed_engines: number;
    total_results: number;
    message: string;
  };
}

export interface SearchProgress {
  engine_name: string;
  status: string;
  results_count: number;
  total_engines: number;
  completed_engines: number;
  total_results: number;
  message: string;
}

export interface SSECompleteEvent {
  type: 'complete';
  data: {
    text: string;
    session_id: string;
    duration_ms: number;
  };
}

export interface SSEErrorEvent {
  type: 'error';
  data: {
    message: string;
    code: string;
  };
}

export type SSEEvent =
  | SSETextEvent
  | SSEToolStartEvent
  | SSEToolEndEvent
  | SSESubagentStartEvent
  | SSESubagentEndEvent
  | SSESearchProgressEvent
  | SSECompleteEvent
  | SSEErrorEvent;

// ============================================
// API Request/Response Types
// ============================================

export interface StartInvestigationRequest {
  query: string;
  context?: Record<string, unknown>;
}

export interface StartInvestigationResponse {
  id: string;
  status: 'pending' | 'streaming';
  stream_url: string;
}

export interface FollowUpRequest {
  query: string;
}

export interface CreateReportRequest {
  investigation_id: string;
  title: string;
  include_sections?: ReportSection['type'][];
}

export interface ListInvestigationsResponse {
  investigations: InvestigationSummary[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================
// IOC Types
// ============================================

export interface IOCEntry {
  type: 'ip' | 'domain' | 'hash' | 'email' | 'url';
  value: string;
  context: string;
  confidence: 'high' | 'medium' | 'low';
}

// ============================================
// UI State Types
// ============================================

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  duration?: number;
}

export interface NavigationItem {
  name: string;
  href: string;
  icon: string;
  badge?: number;
}

// ============================================
// Utility Types
// ============================================

export type AsyncState<T> = {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
};

export type APIResponse<T> = {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
};
