import type {
  InvestigationDetail,
  InvestigationSummary,
  StartInvestigationRequest,
  StartInvestigationResponse,
  FollowUpRequest,
  Report,
  ReportSection,
  ListInvestigationsResponse,
} from '@/types';
import type { GraphData } from '@/types/graph';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

// ============================================
// Investigation API
// ============================================

export const investigationAPI = {
  /**
   * Start a new investigation
   */
  start: async (request: StartInvestigationRequest): Promise<StartInvestigationResponse> => {
    return fetchAPI<StartInvestigationResponse>('/investigations', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Send a follow-up query
   */
  followUp: async (
    investigationId: string,
    request: FollowUpRequest
  ): Promise<StartInvestigationResponse> => {
    return fetchAPI<StartInvestigationResponse>(
      `/investigations/${investigationId}/follow-up`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
  },

  /**
   * Get investigation details
   */
  get: async (investigationId: string): Promise<InvestigationDetail> => {
    return fetchAPI<InvestigationDetail>(`/investigations/${investigationId}`);
  },

  /**
   * Get SSE stream URL for an investigation
   */
  getStreamUrl: (investigationId: string): string => {
    return `${API_BASE}/investigations/${investigationId}/stream`;
  },

  /**
   * List all investigations
   */
  list: async (page = 1, pageSize = 20): Promise<ListInvestigationsResponse> => {
    return fetchAPI<ListInvestigationsResponse>(
      `/investigations?page=${page}&page_size=${pageSize}`
    );
  },

  /**
   * Delete an investigation
   */
  delete: async (investigationId: string): Promise<void> => {
    await fetchAPI(`/investigations/${investigationId}`, {
      method: 'DELETE',
    });
  },
};

/**
 * Get all investigations (alias for investigationAPI.list)
 */
export async function getInvestigations(
  page = 1,
  pageSize = 20
): Promise<ListInvestigationsResponse> {
  return investigationAPI.list(page, pageSize);
}

// ============================================
// History API
// ============================================

export interface HistoryFilters {
  page?: number;
  limit?: number;
  search?: string;
  status?: ('completed' | 'failed' | 'running' | 'pending' | 'streaming' | 'error')[];
  startDate?: string;
  endDate?: string;
  query?: string;
}

export interface HistoryResponse {
  items: InvestigationSummary[];
  total: number;
  page: number;
  totalPages: number;
  page_size: number;
}

export async function getHistory(
  filters: HistoryFilters = {}
): Promise<HistoryResponse> {
  const params = new URLSearchParams();
  const page = filters.page || 1;
  const limit = filters.limit || 20;

  params.set('page', page.toString());
  params.set('page_size', limit.toString());

  if (filters.search) params.set('search', filters.search);
  if (filters.query) params.set('search', filters.query);

  // Backend returns ListInvestigationsResponse with { investigations, total, page, page_size }
  const response = await fetchAPI<ListInvestigationsResponse>(
    `/investigations?${params.toString()}`
  );

  // Client-side filtering for status (backend doesn't support it yet)
  let filtered = response.investigations;
  if (filters.status && filters.status.length > 0) {
    filtered = response.investigations.filter(inv =>
      filters.status!.includes(inv.status as 'completed' | 'failed' | 'running' | 'pending' | 'streaming' | 'error')
    );
  }

  const totalPages = Math.ceil(response.total / response.page_size);

  return {
    items: filtered,
    total: response.total,
    page: response.page,
    totalPages: totalPages,
    page_size: response.page_size,
  };
}

// ============================================
// Graph API
// ============================================

export async function getInvestigationGraph(
  investigationId: string
): Promise<GraphData> {
  return fetchAPI<GraphData>(`/investigations/${investigationId}/graph`);
}

// ============================================
// Reports API
// ============================================

export interface ReportsResponse {
  reports: Report[];
  total: number;
  page: number;
  page_size: number;
}

export async function getReports(
  page = 1,
  pageSize = 20
): Promise<ReportsResponse> {
  return fetchAPI<ReportsResponse>(`/reports?page=${page}&page_size=${pageSize}`);
}

export async function getReport(reportId: string): Promise<Report> {
  return fetchAPI<Report>(`/reports/${reportId}`);
}

export interface CreateReportRequest {
  investigation_id: string;
  title: string;
  sections?: ReportSection[];
}

export async function createReport(request: CreateReportRequest): Promise<Report> {
  return fetchAPI<Report>('/reports', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function updateReport(
  reportId: string,
  updates: Partial<Report>
): Promise<Report> {
  return fetchAPI<Report>(`/reports/${reportId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export async function deleteReport(reportId: string): Promise<void> {
  await fetchAPI(`/reports/${reportId}`, {
    method: 'DELETE',
  });
}

export interface ExportReportOptions {
  format: 'md' | 'pdf' | 'html';
  includeGraph?: boolean;
  includeTimeline?: boolean;
}

export async function exportReport(
  reportId: string,
  options: ExportReportOptions
): Promise<Blob> {
  const params = new URLSearchParams();
  params.set('format', options.format);
  if (options.includeGraph) params.set('include_graph', 'true');
  if (options.includeTimeline) params.set('include_timeline', 'true');

  const response = await fetch(
    `${API_BASE}/reports/${reportId}/export?${params.toString()}`
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Export failed' }));
    throw new Error(error.message || `HTTP ${response.status}`);
  }

  return response.blob();
}
