import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { GraphNode, GraphEdge, GraphData } from '@/types/graph';
import { getInvestigationGraph } from '@/lib/api';

// Define filter types locally since they're different from the API types
interface GraphFilters {
  types: GraphNode['type'][];
  minConfidence?: number;
  searchQuery?: string;
}

// ============================================
// Types
// ============================================

interface GraphState {
  // Graph data
  nodes: GraphNode[];
  edges: GraphEdge[];

  // Selection state
  selectedNodeId: string | null;
  hoveredNodeId: string | null;

  // Filtering
  filters: GraphFilters;

  // UI state
  isLoading: boolean;
  error: Error | null;

  // Layout settings
  layout: 'force' | 'hierarchical' | 'circular' | 'grid';
  zoom: number;
  pan: { x: number; y: number };
}

interface GraphActions {
  // Data loading
  loadGraphData: (investigationId: string) => Promise<void>;
  setGraphData: (data: GraphData) => void;
  clearGraph: () => void;

  // Node operations
  selectNode: (id: string | null) => void;
  setHoveredNode: (id: string | null) => void;
  addNode: (node: GraphNode) => void;
  updateNode: (id: string, updates: Partial<GraphNode>) => void;
  removeNode: (id: string) => void;

  // Edge operations
  addEdge: (edge: GraphEdge) => void;
  removeEdge: (id: string) => void;

  // Filtering
  setFilters: (filters: Partial<GraphFilters>) => void;
  toggleTypeFilter: (type: GraphNode['type']) => void;
  resetFilters: () => void;

  // Layout and view
  setLayout: (layout: GraphState['layout']) => void;
  setZoom: (zoom: number) => void;
  setPan: (pan: { x: number; y: number }) => void;
  resetView: () => void;

  // Computed getters
  getFilteredNodes: () => GraphNode[];
  getFilteredEdges: () => GraphEdge[];
  getNodeById: (id: string) => GraphNode | undefined;
  getConnectedNodes: (nodeId: string) => GraphNode[];
}

export type GraphStore = GraphState & GraphActions;

// ============================================
// Initial State
// ============================================

const defaultFilters: GraphFilters = {
  types: [],
  minConfidence: undefined,
  searchQuery: undefined,
};

const initialState: GraphState = {
  nodes: [],
  edges: [],
  selectedNodeId: null,
  hoveredNodeId: null,
  filters: defaultFilters,
  isLoading: false,
  error: null,
  layout: 'force',
  zoom: 1,
  pan: { x: 0, y: 0 },
};

// ============================================
// Store Implementation
// ============================================

export const useGraphStore = create<GraphStore>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // Load graph data from API
      loadGraphData: async (investigationId: string): Promise<void> => {
        set({ isLoading: true, error: null });

        try {
          const data = await getInvestigationGraph(investigationId);
          set({
            nodes: data.nodes,
            edges: data.edges,
            isLoading: false,
          });
        } catch (error) {
          set({
            isLoading: false,
            error: error instanceof Error ? error : new Error('Failed to load graph data'),
          });
          throw error;
        }
      },

      // Set graph data directly
      setGraphData: (data: GraphData) => {
        set({
          nodes: data.nodes,
          edges: data.edges,
          error: null,
        });
      },

      // Clear graph data
      clearGraph: () => {
        set({
          nodes: [],
          edges: [],
          selectedNodeId: null,
          hoveredNodeId: null,
        });
      },

      // Select a node
      selectNode: (id: string | null) => {
        set({ selectedNodeId: id });
      },

      // Set hovered node
      setHoveredNode: (id: string | null) => {
        set({ hoveredNodeId: id });
      },

      // Add a node
      addNode: (node: GraphNode) => {
        set((state) => ({
          nodes: [...state.nodes, node],
        }));
      },

      // Update a node
      updateNode: (id: string, updates: Partial<GraphNode>) => {
        set((state) => ({
          nodes: state.nodes.map((node) =>
            node.id === id ? { ...node, ...updates } : node
          ),
        }));
      },

      // Remove a node and its connected edges
      removeNode: (id: string) => {
        set((state) => ({
          nodes: state.nodes.filter((node) => node.id !== id),
          edges: state.edges.filter(
            (edge) => edge.source !== id && edge.target !== id
          ),
          selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
        }));
      },

      // Add an edge
      addEdge: (edge: GraphEdge) => {
        set((state) => ({
          edges: [...state.edges, edge],
        }));
      },

      // Remove an edge
      removeEdge: (id: string) => {
        set((state) => ({
          edges: state.edges.filter((edge) => edge.id !== id),
        }));
      },

      // Set filters
      setFilters: (filters: Partial<GraphFilters>) => {
        set((state) => ({
          filters: { ...state.filters, ...filters },
        }));
      },

      // Toggle a type filter
      toggleTypeFilter: (type: GraphNode['type']) => {
        set((state) => {
          const types = state.filters.types.includes(type)
            ? state.filters.types.filter((t) => t !== type)
            : [...state.filters.types, type];

          return {
            filters: { ...state.filters, types },
          };
        });
      },

      // Reset filters to default
      resetFilters: () => {
        set({ filters: defaultFilters });
      },

      // Set layout type
      setLayout: (layout: GraphState['layout']) => {
        set({ layout });
      },

      // Set zoom level
      setZoom: (zoom: number) => {
        set({ zoom: Math.max(0.1, Math.min(3, zoom)) });
      },

      // Set pan position
      setPan: (pan: { x: number; y: number }) => {
        set({ pan });
      },

      // Reset view to default
      resetView: () => {
        set({
          zoom: 1,
          pan: { x: 0, y: 0 },
        });
      },

      // Get filtered nodes
      getFilteredNodes: (): GraphNode[] => {
        const { nodes, filters } = get();

        return nodes.filter((node) => {
          // Filter by type
          if (filters.types.length > 0 && !filters.types.includes(node.type)) {
            return false;
          }

          // Filter by confidence (GraphNode has confidence at top level)
          if (filters.minConfidence !== undefined) {
            const confidenceValue = { high: 3, medium: 2, low: 1 }[node.confidence] || 0;
            if (confidenceValue < filters.minConfidence) {
              return false;
            }
          }

          // Filter by search query
          if (filters.searchQuery) {
            const query = filters.searchQuery.toLowerCase();
            const matchesLabel = node.label.toLowerCase().includes(query);
            const matchesProperties = Object.values(node.properties || {}).some(
              (val) => String(val).toLowerCase().includes(query)
            );
            if (!matchesLabel && !matchesProperties) {
              return false;
            }
          }

          return true;
        });
      },

      // Get filtered edges (only edges between visible nodes)
      getFilteredEdges: (): GraphEdge[] => {
        const { edges } = get();
        const filteredNodes = get().getFilteredNodes();
        const visibleNodeIds = new Set(filteredNodes.map((n) => n.id));

        return edges.filter(
          (edge) =>
            visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
        );
      },

      // Get node by ID
      getNodeById: (id: string): GraphNode | undefined => {
        return get().nodes.find((node) => node.id === id);
      },

      // Get connected nodes
      getConnectedNodes: (nodeId: string): GraphNode[] => {
        const { nodes, edges } = get();
        const connectedIds = new Set<string>();

        edges.forEach((edge) => {
          if (edge.source === nodeId) {
            connectedIds.add(edge.target);
          } else if (edge.target === nodeId) {
            connectedIds.add(edge.source);
          }
        });

        return nodes.filter((node) => connectedIds.has(node.id));
      },
    }),
    { name: 'GraphStore' }
  )
);

// ============================================
// Selectors
// ============================================

export const selectNodes = (state: GraphStore) => state.nodes;
export const selectEdges = (state: GraphStore) => state.edges;
export const selectSelectedNodeId = (state: GraphStore) => state.selectedNodeId;
export const selectFilters = (state: GraphStore) => state.filters;
export const selectIsLoading = (state: GraphStore) => state.isLoading;
export const selectLayout = (state: GraphStore) => state.layout;
export const selectZoom = (state: GraphStore) => state.zoom;

// Selector for selected node data
export const selectSelectedNode = (state: GraphStore): GraphNode | undefined => {
  if (!state.selectedNodeId) return undefined;
  return state.nodes.find((node) => node.id === state.selectedNodeId);
};

// Selector for node count by type
export const selectNodeCountByType = (
  state: GraphStore
): Record<GraphNode['type'], number> => {
  const counts: Record<string, number> = {};

  state.nodes.forEach((node) => {
    counts[node.type] = (counts[node.type] || 0) + 1;
  });

  return counts as Record<GraphNode['type'], number>;
};

export default useGraphStore;
