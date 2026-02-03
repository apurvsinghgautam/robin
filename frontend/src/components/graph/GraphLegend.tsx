'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NODE_STYLES, EDGE_STYLES, CONFIDENCE_COLORS, GraphNode, GraphEdge } from '@/types/graph';

interface GraphLegendProps {
  className?: string;
}

export default function GraphLegend({ className }: GraphLegendProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const nodeTypes = Object.entries(NODE_STYLES) as [GraphNode['type'], typeof NODE_STYLES[GraphNode['type']]][];
  const edgeTypes = Object.entries(EDGE_STYLES) as [GraphEdge['type'], typeof EDGE_STYLES[GraphEdge['type']]][];
  const confidenceLevels = Object.entries(CONFIDENCE_COLORS) as [GraphNode['confidence'], string][];

  return (
    <div className={`bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700 ${className}`}>
      <Button
        variant="ghost"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 h-auto text-slate-200 hover:bg-slate-700/50"
      >
        <span className="font-medium">Legend</span>
        {isExpanded ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </Button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-4">
          {/* Node Types */}
          <div>
            <h4 className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">
              Node Types
            </h4>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              {nodeTypes.map(([type, style]) => (
                <div key={type} className="flex items-center gap-2">
                  <NodeShape shape={style.shape} color={style.color} />
                  <span className="text-xs text-slate-300">{style.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Edge Types */}
          <div>
            <h4 className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">
              Relationships
            </h4>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
              {edgeTypes.map(([type, style]) => (
                <div key={type} className="flex items-center gap-2">
                  <div className="flex items-center">
                    <div
                      className="w-4 h-0.5"
                      style={{ backgroundColor: style.color }}
                    />
                    <div
                      className="w-0 h-0 border-t-[3px] border-t-transparent border-b-[3px] border-b-transparent border-l-[5px]"
                      style={{ borderLeftColor: style.color }}
                    />
                  </div>
                  <span className="text-xs text-slate-300">{style.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Confidence */}
          <div>
            <h4 className="text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">
              Confidence
            </h4>
            <div className="flex items-center gap-4">
              {confidenceLevels.map(([level, color]) => (
                <div key={level} className="flex items-center gap-1.5">
                  <div
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-xs text-slate-300 capitalize">{level}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Helper component for node shapes
function NodeShape({ shape, color }: { shape: string; color: string }) {
  const size = 12;

  switch (shape) {
    case 'diamond':
      return (
        <svg width={size} height={size} viewBox="0 0 12 12">
          <polygon
            points="6,0 12,6 6,12 0,6"
            fill={color}
          />
        </svg>
      );
    case 'hexagon':
      return (
        <svg width={size} height={size} viewBox="0 0 12 12">
          <polygon
            points="3,0 9,0 12,6 9,12 3,12 0,6"
            fill={color}
          />
        </svg>
      );
    case 'rectangle':
      return (
        <div
          className="w-3 h-3 rounded-sm"
          style={{ backgroundColor: color }}
        />
      );
    case 'ellipse':
    default:
      return (
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: color }}
        />
      );
  }
}
