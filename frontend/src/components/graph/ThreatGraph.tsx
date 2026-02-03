'use client';

import React, { useRef, useEffect, useCallback, useState } from 'react';
import CytoscapeComponent from 'react-cytoscapejs';
import cytoscape, { Core, NodeSingular, EventObject } from 'cytoscape';
import cola from 'cytoscape-cola';
import { GraphNode, GraphEdge, NODE_STYLES, EDGE_STYLES } from '@/types/graph';

// Register cola layout
if (typeof cytoscape('layout', 'cola') === 'undefined') {
  cytoscape.use(cola);
}

export type LayoutType = 'cola' | 'cose' | 'circle' | 'grid' | 'breadthfirst';

interface ThreatGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  layout?: LayoutType;
  onNodeSelect?: (node: GraphNode | null) => void;
  selectedNodeId?: string | null;
  showEdgeLabels?: boolean;
  filteredNodeTypes?: GraphNode['type'][];
  filteredConfidence?: GraphNode['confidence'][];
  searchQuery?: string;
}

const stylesheet: cytoscape.StylesheetStyle[] = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      'label': 'data(label)',
      'shape': 'data(shape)' as any,
      'width': 45,
      'height': 45,
      'font-size': '10px',
      'text-valign': 'bottom',
      'text-halign': 'center',
      'text-margin-y': 5,
      'color': '#e2e8f0',
      'text-outline-color': '#0f172a',
      'text-outline-width': 1,
      'border-width': 2,
      'border-color': 'data(borderColor)',
      'transition-property': 'background-color, border-color, width, height',
      'transition-duration': 200,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-width': 4,
      'border-color': '#f8fafc',
      'width': 55,
      'height': 55,
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-width': 3,
      'border-color': '#22d3ee',
    },
  },
  {
    selector: 'node.faded',
    style: {
      'opacity': 0.3,
    },
  },
  {
    selector: 'edge',
    style: {
      'width': 'data(width)',
      'line-color': 'data(color)',
      'target-arrow-color': 'data(color)',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      'opacity': 0.8,
      'transition-property': 'opacity, line-color',
      'transition-duration': 200,
    },
  },
  {
    selector: 'edge.labeled',
    style: {
      'label': 'data(label)',
      'font-size': '8px',
      'text-rotation': 'autorotate',
      'text-margin-y': -8,
      'color': '#94a3b8',
    },
  },
  {
    selector: 'edge:selected',
    style: {
      'opacity': 1,
      'width': 4,
    },
  },
  {
    selector: 'edge.faded',
    style: {
      'opacity': 0.15,
    },
  },
];

export default function ThreatGraph({
  nodes,
  edges,
  layout = 'cola',
  onNodeSelect,
  selectedNodeId,
  showEdgeLabels = false,
  filteredNodeTypes,
  filteredConfidence,
  searchQuery,
}: ThreatGraphProps) {
  const cyRef = useRef<Core | null>(null);
  const [isReady, setIsReady] = useState(false);

  // Transform nodes for Cytoscape
  const cyNodes = nodes
    .filter((node) => {
      if (filteredNodeTypes && filteredNodeTypes.length > 0 && !filteredNodeTypes.includes(node.type)) {
        return false;
      }
      if (filteredConfidence && filteredConfidence.length > 0 && !filteredConfidence.includes(node.confidence)) {
        return false;
      }
      return true;
    })
    .map((node) => {
      const style = NODE_STYLES[node.type];
      return {
        data: {
          id: node.id,
          label: node.label,
          color: style.color,
          shape: style.shape,
          borderColor: style.color,
          nodeType: node.type,
          confidence: node.confidence,
          properties: node.properties,
        },
      };
    });

  // Transform edges for Cytoscape
  const visibleNodeIds = new Set(cyNodes.map((n) => n.data.id));
  const cyEdges = edges
    .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
    .map((edge) => {
      const style = EDGE_STYLES[edge.type];
      return {
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: style.label,
          color: style.color,
          width: Math.max(1, Math.min(edge.weight * 2, 6)),
          edgeType: edge.type,
        },
      };
    });

  const elements = [...cyNodes, ...cyEdges];

  const layoutConfig = useCallback(() => {
    switch (layout) {
      case 'cola':
        return {
          name: 'cola',
          animate: true,
          randomize: false,
          maxSimulationTime: 2000,
          nodeSpacing: 40,
          edgeLengthVal: 100,
          fit: true,
          padding: 50,
        };
      case 'cose':
        return {
          name: 'cose',
          animate: true,
          randomize: false,
          nodeRepulsion: () => 8000,
          nodeOverlap: 20,
          idealEdgeLength: () => 80,
          fit: true,
          padding: 50,
        };
      case 'circle':
        return {
          name: 'circle',
          animate: true,
          fit: true,
          padding: 50,
        };
      case 'grid':
        return {
          name: 'grid',
          animate: true,
          fit: true,
          padding: 50,
          avoidOverlap: true,
        };
      case 'breadthfirst':
        return {
          name: 'breadthfirst',
          animate: true,
          fit: true,
          padding: 50,
          directed: true,
        };
      default:
        return { name: 'cola', animate: true, fit: true, padding: 50 };
    }
  }, [layout]);

  // Handle node selection
  const handleNodeTap = useCallback(
    (event: EventObject) => {
      const node = event.target as NodeSingular;
      const nodeData = node.data();

      if (onNodeSelect) {
        const graphNode: GraphNode = {
          id: nodeData.id,
          type: nodeData.nodeType,
          label: nodeData.label,
          properties: nodeData.properties,
          confidence: nodeData.confidence,
        };
        onNodeSelect(graphNode);
      }
    },
    [onNodeSelect]
  );

  const handleBackgroundTap = useCallback(() => {
    if (onNodeSelect) {
      onNodeSelect(null);
    }
  }, [onNodeSelect]);

  // Initialize Cytoscape
  const handleCyInit = useCallback(
    (cy: Core) => {
      cyRef.current = cy;
      setIsReady(true);

      cy.on('tap', 'node', handleNodeTap);
      cy.on('tap', (event) => {
        if (event.target === cy) {
          handleBackgroundTap();
        }
      });

      // Run layout after init
      cy.layout(layoutConfig()).run();
    },
    [handleNodeTap, handleBackgroundTap, layoutConfig]
  );

  // Update layout when changed
  useEffect(() => {
    if (cyRef.current && isReady) {
      cyRef.current.layout(layoutConfig()).run();
    }
  }, [layout, layoutConfig, isReady]);

  // Handle edge labels toggle
  useEffect(() => {
    if (cyRef.current && isReady) {
      if (showEdgeLabels) {
        cyRef.current.edges().addClass('labeled');
      } else {
        cyRef.current.edges().removeClass('labeled');
      }
    }
  }, [showEdgeLabels, isReady]);

  // Handle search highlighting
  useEffect(() => {
    if (cyRef.current && isReady) {
      cyRef.current.nodes().removeClass('highlighted faded');

      if (searchQuery && searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        cyRef.current.nodes().forEach((node) => {
          const label = node.data('label')?.toLowerCase() || '';
          if (label.includes(query)) {
            node.addClass('highlighted');
          } else {
            node.addClass('faded');
          }
        });
        cyRef.current.edges().addClass('faded');
      } else {
        cyRef.current.edges().removeClass('faded');
      }
    }
  }, [searchQuery, isReady]);

  // Handle selected node
  useEffect(() => {
    if (cyRef.current && isReady) {
      cyRef.current.nodes().unselect();
      if (selectedNodeId) {
        const node = cyRef.current.getElementById(selectedNodeId);
        if (node.length > 0) {
          node.select();
        }
      }
    }
  }, [selectedNodeId, isReady]);

  return (
    <div className="w-full h-full bg-slate-900 rounded-lg overflow-hidden">
      <CytoscapeComponent
        elements={elements}
        stylesheet={stylesheet}
        style={{ width: '100%', height: '100%' }}
        cy={handleCyInit}
        wheelSensitivity={0.3}
        minZoom={0.2}
        maxZoom={3}
        boxSelectionEnabled={false}
      />
    </div>
  );
}

// Export ref methods for external control
export function useThreatGraph() {
  const cyRef = useRef<Core | null>(null);

  const zoomIn = () => {
    if (cyRef.current) {
      const currentZoom = cyRef.current.zoom();
      cyRef.current.animate({ zoom: currentZoom * 1.3, duration: 200 });
    }
  };

  const zoomOut = () => {
    if (cyRef.current) {
      const currentZoom = cyRef.current.zoom();
      cyRef.current.animate({ zoom: currentZoom / 1.3, duration: 200 });
    }
  };

  const fitToScreen = () => {
    if (cyRef.current) {
      cyRef.current.animate({ fit: { eles: cyRef.current.elements(), padding: 50 }, duration: 300 });
    }
  };

  const exportPNG = () => {
    if (cyRef.current) {
      return cyRef.current.png({ full: true, scale: 2, bg: '#0f172a' });
    }
    return null;
  };

  const setCy = (cy: Core) => {
    cyRef.current = cy;
  };

  return { zoomIn, zoomOut, fitToScreen, exportPNG, setCy, cyRef };
}
