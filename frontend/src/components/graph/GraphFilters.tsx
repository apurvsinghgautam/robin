'use client';

import React from 'react';
import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { ScrollArea } from '@/components/ui/scroll-area';
import { GraphNode, NODE_STYLES, CONFIDENCE_COLORS } from '@/types/graph';

interface GraphFiltersProps {
  nodeTypes: GraphNode['type'][];
  selectedNodeTypes: GraphNode['type'][];
  onNodeTypesChange: (types: GraphNode['type'][]) => void;
  confidenceLevels: GraphNode['confidence'][];
  selectedConfidence: GraphNode['confidence'][];
  onConfidenceChange: (levels: GraphNode['confidence'][]) => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  showEdgeLabels: boolean;
  onShowEdgeLabelsChange: (show: boolean) => void;
}

export default function GraphFilters({
  nodeTypes,
  selectedNodeTypes,
  onNodeTypesChange,
  confidenceLevels,
  selectedConfidence,
  onConfidenceChange,
  searchQuery,
  onSearchChange,
  showEdgeLabels,
  onShowEdgeLabelsChange,
}: GraphFiltersProps) {
  const handleNodeTypeToggle = (type: GraphNode['type']) => {
    if (selectedNodeTypes.includes(type)) {
      onNodeTypesChange(selectedNodeTypes.filter((t) => t !== type));
    } else {
      onNodeTypesChange([...selectedNodeTypes, type]);
    }
  };

  const handleConfidenceToggle = (level: GraphNode['confidence']) => {
    if (selectedConfidence.includes(level)) {
      onConfidenceChange(selectedConfidence.filter((l) => l !== level));
    } else {
      onConfidenceChange([...selectedConfidence, level]);
    }
  };

  const handleSelectAllTypes = () => {
    onNodeTypesChange([...nodeTypes]);
  };

  const handleClearTypes = () => {
    onNodeTypesChange([]);
  };

  const handleClearSearch = () => {
    onSearchChange('');
  };

  return (
    <div className="w-64 bg-slate-800 border-l border-slate-700 flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h3 className="font-semibold text-slate-200 mb-3">Filters</h3>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 pr-8 bg-slate-700 border-slate-600 text-slate-200 placeholder:text-slate-400"
          />
          {searchQuery && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleClearSearch}
              className="absolute right-1 top-1 h-6 w-6 text-slate-400 hover:text-slate-200"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Node Types */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-slate-300">Node Types</h4>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSelectAllTypes}
                  className="h-6 px-2 text-xs text-slate-400 hover:text-slate-200"
                >
                  All
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearTypes}
                  className="h-6 px-2 text-xs text-slate-400 hover:text-slate-200"
                >
                  None
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              {nodeTypes.map((type) => {
                const style = NODE_STYLES[type];
                return (
                  <div key={type} className="flex items-center gap-2">
                    <Checkbox
                      id={`type-${type}`}
                      checked={selectedNodeTypes.includes(type)}
                      onCheckedChange={() => handleNodeTypeToggle(type)}
                      className="border-slate-500 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                    />
                    <div
                      className="w-3 h-3 rounded-sm"
                      style={{ backgroundColor: style.color }}
                    />
                    <Label
                      htmlFor={`type-${type}`}
                      className="text-sm text-slate-300 cursor-pointer"
                    >
                      {style.label}
                    </Label>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Confidence Levels */}
          <div>
            <h4 className="text-sm font-medium text-slate-300 mb-3">Confidence</h4>
            <div className="space-y-2">
              {confidenceLevels.map((level) => (
                <div key={level} className="flex items-center gap-2">
                  <Checkbox
                    id={`confidence-${level}`}
                    checked={selectedConfidence.includes(level)}
                    onCheckedChange={() => handleConfidenceToggle(level)}
                    className="border-slate-500 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                  />
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: CONFIDENCE_COLORS[level] }}
                  />
                  <Label
                    htmlFor={`confidence-${level}`}
                    className="text-sm text-slate-300 cursor-pointer capitalize"
                  >
                    {level}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          {/* Display Options */}
          <div>
            <h4 className="text-sm font-medium text-slate-300 mb-3">Display</h4>
            <div className="flex items-center justify-between">
              <Label
                htmlFor="edge-labels"
                className="text-sm text-slate-300 cursor-pointer"
              >
                Show edge labels
              </Label>
              <Switch
                id="edge-labels"
                checked={showEdgeLabels}
                onCheckedChange={onShowEdgeLabelsChange}
                className="data-[state=checked]:bg-blue-600"
              />
            </div>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
