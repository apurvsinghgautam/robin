'use client';

import React from 'react';
import { X, ExternalLink, Link2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { GraphNode, GraphEdge, NODE_STYLES, CONFIDENCE_COLORS, EDGE_STYLES } from '@/types/graph';

interface NodeDetailsProps {
  node: GraphNode | null;
  edges: GraphEdge[];
  nodes: GraphNode[];
  onClose: () => void;
  onNodeClick?: (nodeId: string) => void;
  investigationId?: string;
}

export default function NodeDetails({
  node,
  edges,
  nodes,
  onClose,
  onNodeClick,
  investigationId,
}: NodeDetailsProps) {
  if (!node) return null;

  const nodeStyle = NODE_STYLES[node.type];

  // Get connected nodes
  const connectedEdges = edges.filter(
    (edge) => edge.source === node.id || edge.target === node.id
  );

  const connectedNodes = connectedEdges.map((edge) => {
    const connectedId = edge.source === node.id ? edge.target : edge.source;
    const connectedNode = nodes.find((n) => n.id === connectedId);
    const direction = edge.source === node.id ? 'outgoing' : 'incoming';
    return {
      edge,
      node: connectedNode,
      direction,
    };
  });

  const formatPropertyValue = (value: any): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  return (
    <div className="w-80 bg-slate-800 border-l border-slate-700 flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-4 h-4 rounded-sm flex-shrink-0"
              style={{ backgroundColor: nodeStyle.color }}
            />
            <Badge
              variant="outline"
              className="text-xs border-slate-600 text-slate-300"
            >
              {nodeStyle.label}
            </Badge>
          </div>
          <h3 className="font-semibold text-slate-100 text-lg truncate" title={node.label}>
            {node.label}
          </h3>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-8 w-8 text-slate-400 hover:text-slate-200 flex-shrink-0"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Confidence */}
          <div>
            <h4 className="text-sm font-medium text-slate-400 mb-2">Confidence</h4>
            <Badge
              className="capitalize"
              style={{
                backgroundColor: CONFIDENCE_COLORS[node.confidence],
                color: node.confidence === 'medium' ? '#1e293b' : 'white',
              }}
            >
              {node.confidence}
            </Badge>
          </div>

          {/* Properties */}
          {Object.keys(node.properties).length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-400 mb-2">Properties</h4>
              <div className="space-y-2">
                {Object.entries(node.properties).map(([key, value]) => (
                  <div key={key} className="bg-slate-700/50 rounded p-2">
                    <div className="text-xs text-slate-400 mb-0.5 capitalize">
                      {key.replace(/_/g, ' ')}
                    </div>
                    <div className="text-sm text-slate-200 break-all">
                      {formatPropertyValue(value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Separator className="bg-slate-700" />

          {/* Connected Nodes */}
          <div>
            <h4 className="text-sm font-medium text-slate-400 mb-2">
              Connections ({connectedNodes.length})
            </h4>
            {connectedNodes.length === 0 ? (
              <p className="text-sm text-slate-500 italic">No connections</p>
            ) : (
              <div className="space-y-2">
                {connectedNodes.map(({ edge, node: connNode, direction }) => {
                  if (!connNode) return null;
                  const connNodeStyle = NODE_STYLES[connNode.type];
                  const edgeStyle = EDGE_STYLES[edge.type];

                  return (
                    <button
                      key={edge.id}
                      onClick={() => onNodeClick?.(connNode.id)}
                      className="w-full text-left p-2 rounded bg-slate-700/50 hover:bg-slate-700 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div
                          className="w-2.5 h-2.5 rounded-sm"
                          style={{ backgroundColor: connNodeStyle.color }}
                        />
                        <span className="text-sm text-slate-200 truncate flex-1">
                          {connNode.label}
                        </span>
                        <Link2 className="h-3 w-3 text-slate-500" />
                      </div>
                      <div className="flex items-center gap-1 text-xs text-slate-400">
                        <span>{direction === 'outgoing' ? 'outgoing' : 'incoming'}:</span>
                        <span style={{ color: edgeStyle.color }}>{edgeStyle.label}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Investigation Link */}
          {investigationId && (
            <>
              <Separator className="bg-slate-700" />
              <div>
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full border-slate-600 text-slate-300 hover:bg-slate-700"
                  asChild
                >
                  <a href={`/investigations/${investigationId}`}>
                    <ExternalLink className="h-4 w-4 mr-2" />
                    View Investigation Source
                  </a>
                </Button>
              </div>
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
