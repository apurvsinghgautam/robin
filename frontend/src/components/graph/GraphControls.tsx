'use client';

import React from 'react';
import { ZoomIn, ZoomOut, Maximize2, Download, Layout, Minimize2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { LayoutType } from './ThreatGraph';

interface GraphControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitToScreen: () => void;
  onExportPNG: () => void;
  onLayoutChange: (layout: LayoutType) => void;
  currentLayout: LayoutType;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
}

const LAYOUTS: { value: LayoutType; label: string }[] = [
  { value: 'cola', label: 'Force (Cola)' },
  { value: 'cose', label: 'Force (Cose)' },
  { value: 'circle', label: 'Circle' },
  { value: 'grid', label: 'Grid' },
  { value: 'breadthfirst', label: 'Hierarchy' },
];

export default function GraphControls({
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  onExportPNG,
  onLayoutChange,
  currentLayout,
  isFullscreen,
  onToggleFullscreen,
}: GraphControlsProps) {
  return (
    <TooltipProvider>
      <div className="flex items-center gap-2 p-2 bg-slate-800/90 backdrop-blur-sm rounded-lg border border-slate-700">
        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onZoomIn}
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <ZoomIn className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Zoom In</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onZoomOut}
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <ZoomOut className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Zoom Out</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onFitToScreen}
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <Maximize2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Fit to Screen</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Divider */}
        <div className="w-px h-6 bg-slate-600" />

        {/* Layout Selector */}
        <div className="flex items-center gap-2">
          <Layout className="h-4 w-4 text-slate-400" />
          <Select value={currentLayout} onValueChange={(value) => onLayoutChange(value as LayoutType)}>
            <SelectTrigger className="w-[130px] h-8 bg-slate-700 border-slate-600 text-slate-200">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-slate-800 border-slate-700">
              {LAYOUTS.map((layout) => (
                <SelectItem
                  key={layout.value}
                  value={layout.value}
                  className="text-slate-200 focus:bg-slate-700 focus:text-white"
                >
                  {layout.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Divider */}
        <div className="w-px h-6 bg-slate-600" />

        {/* Export and Fullscreen */}
        <div className="flex items-center gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onExportPNG}
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-700"
              >
                <Download className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>Export as PNG</p>
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleFullscreen}
                className="h-8 w-8 text-slate-300 hover:text-white hover:bg-slate-700"
              >
                {isFullscreen ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>
              <p>{isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}</p>
            </TooltipContent>
          </Tooltip>
        </div>
      </div>
    </TooltipProvider>
  );
}
