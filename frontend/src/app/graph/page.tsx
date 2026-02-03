'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Core } from 'cytoscape';
import { Network, RefreshCw } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import ThreatGraph, { LayoutType } from '@/components/graph/ThreatGraph';
import GraphControls from '@/components/graph/GraphControls';
import GraphFilters from '@/components/graph/GraphFilters';
import NodeDetails from '@/components/graph/NodeDetails';
import GraphLegend from '@/components/graph/GraphLegend';
import { GraphNode, GraphEdge, NODE_STYLES } from '@/types/graph';
import { InvestigationSummary } from '@/types';
import { getInvestigations, getInvestigationGraph } from '@/lib/api';
import { downloadBlob } from '@/lib/utils';

// All node types for filtering
const ALL_NODE_TYPES: GraphNode['type'][] = [
  'threat_actor',
  'malware',
  'ioc_ip',
  'ioc_domain',
  'ioc_hash',
  'ioc_email',
  'marketplace',
  'vendor',
  'cve',
];

const ALL_CONFIDENCE_LEVELS: GraphNode['confidence'][] = ['high', 'medium', 'low'];

export default function GraphPage() {
  // State
  const [investigations, setInvestigations] = useState<InvestigationSummary[]>([]);
  const [selectedInvestigationId, setSelectedInvestigationId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Graph control state
  const [layout, setLayout] = useState<LayoutType>('cola');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Filter state
  const [filteredNodeTypes, setFilteredNodeTypes] = useState<GraphNode['type'][]>([...ALL_NODE_TYPES]);
  const [filteredConfidence, setFilteredConfidence] = useState<GraphNode['confidence'][]>([...ALL_CONFIDENCE_LEVELS]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);

  // Cytoscape ref
  const cyRef = useRef<Core | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Load investigations on mount
  useEffect(() => {
    async function loadInvestigations() {
      try {
        const response = await getInvestigations();
        const invList = response.investigations || [];
        setInvestigations(invList);
        if (invList.length > 0) {
          setSelectedInvestigationId(invList[0].id);
        }
      } catch (err) {
        console.error('Failed to load investigations:', err);
        // Use mock data for development
        const mockInvestigations: InvestigationSummary[] = [
          {
            id: '1',
            initial_query: 'ransomware investigation',
            status: 'completed',
            created_at: new Date().toISOString(),
            entity_count: 15,
          },
          {
            id: '2',
            initial_query: 'marketplace vendor analysis',
            status: 'completed',
            created_at: new Date().toISOString(),
            entity_count: 8,
          },
        ];
        setInvestigations(mockInvestigations);
        setSelectedInvestigationId('1');
      }
    }
    loadInvestigations();
  }, []);

  // Load graph data when investigation changes
  useEffect(() => {
    async function loadGraph() {
      if (!selectedInvestigationId) return;

      setLoading(true);
      setError(null);

      try {
        const data = await getInvestigationGraph(selectedInvestigationId);
        setNodes(data.nodes);
        setEdges(data.edges);
      } catch (err) {
        console.error('Failed to load graph:', err);
        // Use mock data for development
        const mockNodes: GraphNode[] = [
          { id: '1', type: 'threat_actor', label: 'APT28', properties: { aliases: ['Fancy Bear', 'Sofacy'], country: 'Russia' }, confidence: 'high' },
          { id: '2', type: 'malware', label: 'X-Agent', properties: { family: 'Trojan', firstSeen: '2015' }, confidence: 'high' },
          { id: '3', type: 'ioc_domain', label: 'malware-c2.example.com', properties: { registrar: 'Unknown' }, confidence: 'medium' },
          { id: '4', type: 'ioc_ip', label: '192.168.1.100', properties: { asn: 'AS12345' }, confidence: 'medium' },
          { id: '5', type: 'cve', label: 'CVE-2023-1234', properties: { cvss: 9.8, description: 'Critical RCE' }, confidence: 'high' },
          { id: '6', type: 'marketplace', label: 'DarkMarket', properties: { status: 'active', currency: 'BTC' }, confidence: 'medium' },
          { id: '7', type: 'vendor', label: 'CyberCriminal_X', properties: { rating: 4.5, salesCount: 150 }, confidence: 'low' },
          { id: '8', type: 'ioc_hash', label: 'abc123...def789', properties: { type: 'SHA256', malwareFamily: 'X-Agent' }, confidence: 'high' },
        ];

        const mockEdges: GraphEdge[] = [
          { id: 'e1', source: '1', target: '2', type: 'uses', weight: 1 },
          { id: 'e2', source: '2', target: '3', type: 'communicates_with', weight: 0.8 },
          { id: 'e3', source: '3', target: '4', type: 'associated_with', weight: 0.7 },
          { id: 'e4', source: '1', target: '5', type: 'exploits', weight: 0.9 },
          { id: 'e5', source: '7', target: '6', type: 'sells_on', weight: 0.6 },
          { id: 'e6', source: '7', target: '2', type: 'sells_on', weight: 0.5 },
          { id: 'e7', source: '2', target: '8', type: 'associated_with', weight: 1 },
          { id: 'e8', source: '1', target: '4', type: 'targets', weight: 0.7 },
        ];

        setNodes(mockNodes);
        setEdges(mockEdges);
      } finally {
        setLoading(false);
      }
    }

    loadGraph();
  }, [selectedInvestigationId]);

  // Graph control handlers
  const handleZoomIn = useCallback(() => {
    if (cyRef.current) {
      const currentZoom = cyRef.current.zoom();
      cyRef.current.animate({ zoom: currentZoom * 1.3, duration: 200 });
    }
  }, []);

  const handleZoomOut = useCallback(() => {
    if (cyRef.current) {
      const currentZoom = cyRef.current.zoom();
      cyRef.current.animate({ zoom: currentZoom / 1.3, duration: 200 });
    }
  }, []);

  const handleFitToScreen = useCallback(() => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 50);
    }
  }, []);

  const handleExportPNG = useCallback(() => {
    if (cyRef.current) {
      const png = cyRef.current.png({ full: true, scale: 2, bg: '#0f172a' });
      // Convert base64 to blob
      const byteString = atob(png.split(',')[1]);
      const mimeString = png.split(',')[0].split(':')[1].split(';')[0];
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
      }
      const blob = new Blob([ab], { type: mimeString });
      downloadBlob(blob, `threat-graph-${selectedInvestigationId}.png`);
    }
  }, [selectedInvestigationId]);

  const handleToggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;

    if (!isFullscreen) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // Node selection handler
  const handleNodeSelect = useCallback((node: GraphNode | null) => {
    setSelectedNode(node);
  }, []);

  const handleNodeClick = useCallback((nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId);
    if (node) {
      setSelectedNode(node);
    }
  }, [nodes]);

  // Get unique node types present in current graph
  const presentNodeTypes = Array.from(new Set(nodes.map((n) => n.type)));

  return (
    <div ref={containerRef} className="h-screen flex flex-col bg-slate-950">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Network className="h-6 w-6 text-blue-500" />
          <h1 className="text-xl font-semibold text-slate-100">Threat Graph</h1>
        </div>

        <div className="flex items-center gap-4">
          {/* Investigation Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Investigation:</span>
            <Select
              value={selectedInvestigationId || undefined}
              onValueChange={setSelectedInvestigationId}
            >
              <SelectTrigger className="w-[250px] bg-slate-800 border-slate-700 text-slate-200">
                <SelectValue placeholder="Select investigation" />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                {investigations.map((inv) => (
                  <SelectItem
                    key={inv.id}
                    value={inv.id}
                    className="text-slate-200 focus:bg-slate-700 focus:text-white"
                  >
                    {inv.initial_query || inv.query}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Button
            variant="outline"
            size="icon"
            onClick={() => setSelectedInvestigationId(selectedInvestigationId)}
            disabled={loading}
            className="border-slate-700 text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Filters Sidebar */}
        <GraphFilters
          nodeTypes={presentNodeTypes.length > 0 ? presentNodeTypes : ALL_NODE_TYPES}
          selectedNodeTypes={filteredNodeTypes}
          onNodeTypesChange={setFilteredNodeTypes}
          confidenceLevels={ALL_CONFIDENCE_LEVELS}
          selectedConfidence={filteredConfidence}
          onConfidenceChange={setFilteredConfidence}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          showEdgeLabels={showEdgeLabels}
          onShowEdgeLabelsChange={setShowEdgeLabels}
        />

        {/* Graph Area */}
        <div className="flex-1 relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
              <div className="flex flex-col items-center gap-3">
                <RefreshCw className="h-8 w-8 text-blue-500 animate-spin" />
                <span className="text-slate-400">Loading graph...</span>
              </div>
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
              <div className="text-center">
                <p className="text-red-400 mb-2">{error}</p>
                <Button
                  variant="outline"
                  onClick={() => setSelectedInvestigationId(selectedInvestigationId)}
                  className="border-slate-700"
                >
                  Retry
                </Button>
              </div>
            </div>
          ) : nodes.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
              <div className="text-center">
                <Network className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400">No graph data available</p>
                <p className="text-sm text-slate-500">Select an investigation to view its threat graph</p>
              </div>
            </div>
          ) : (
            <ThreatGraph
              nodes={nodes}
              edges={edges}
              layout={layout}
              onNodeSelect={handleNodeSelect}
              selectedNodeId={selectedNode?.id}
              showEdgeLabels={showEdgeLabels}
              filteredNodeTypes={filteredNodeTypes}
              filteredConfidence={filteredConfidence}
              searchQuery={searchQuery}
            />
          )}

          {/* Controls Overlay */}
          <div className="absolute top-4 left-4 z-10">
            <GraphControls
              onZoomIn={handleZoomIn}
              onZoomOut={handleZoomOut}
              onFitToScreen={handleFitToScreen}
              onExportPNG={handleExportPNG}
              onLayoutChange={setLayout}
              currentLayout={layout}
              isFullscreen={isFullscreen}
              onToggleFullscreen={handleToggleFullscreen}
            />
          </div>

          {/* Legend Overlay */}
          <div className="absolute bottom-4 left-4 z-10">
            <GraphLegend />
          </div>

          {/* Stats Overlay */}
          {nodes.length > 0 && (
            <div className="absolute top-4 right-4 z-10 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700 px-3 py-2">
              <div className="flex items-center gap-4 text-sm">
                <span className="text-slate-400">
                  <span className="text-slate-200 font-medium">{nodes.length}</span> nodes
                </span>
                <span className="text-slate-400">
                  <span className="text-slate-200 font-medium">{edges.length}</span> edges
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Node Details Sidebar */}
        {selectedNode && (
          <NodeDetails
            node={selectedNode}
            edges={edges}
            nodes={nodes}
            onClose={() => setSelectedNode(null)}
            onNodeClick={handleNodeClick}
            investigationId={selectedInvestigationId || undefined}
          />
        )}
      </div>
    </div>
  );
}
