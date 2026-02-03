'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Wrench,
  ArrowRight,
  Network,
  FileText,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { formatRelativeTime, formatDuration, truncate } from '@/lib/utils';

interface HistoryCardProps {
  id: string;
  query: string;
  status: 'pending' | 'streaming' | 'completed' | 'error' | 'running' | 'failed';
  created_at: string;
  duration_ms?: number;
  entity_count?: number;
}

const STATUS_CONFIG = {
  completed: {
    icon: CheckCircle2,
    label: 'Completed',
    color: 'bg-green-600 text-white',
    iconColor: 'text-green-500',
  },
  error: {
    icon: XCircle,
    label: 'Error',
    color: 'bg-red-600 text-white',
    iconColor: 'text-red-500',
  },
  failed: {
    icon: XCircle,
    label: 'Failed',
    color: 'bg-red-600 text-white',
    iconColor: 'text-red-500',
  },
  streaming: {
    icon: Loader2,
    label: 'Running',
    color: 'bg-blue-600 text-white',
    iconColor: 'text-blue-500',
  },
  running: {
    icon: Loader2,
    label: 'Running',
    color: 'bg-blue-600 text-white',
    iconColor: 'text-blue-500',
  },
  pending: {
    icon: Clock,
    label: 'Pending',
    color: 'bg-yellow-600 text-white',
    iconColor: 'text-yellow-500',
  },
};

export default function HistoryCard({
  id,
  query,
  status,
  created_at,
  duration_ms,
  entity_count,
}: HistoryCardProps) {
  const router = useRouter();
  const statusConfig = STATUS_CONFIG[status];
  const StatusIcon = statusConfig.icon;

  const handleClick = () => {
    router.push(`/investigations/${id}`);
  };

  const handleViewGraph = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/graph?investigation=${id}`);
  };

  const handleCreateReport = (e: React.MouseEvent) => {
    e.stopPropagation();
    router.push(`/reports/builder?investigation=${id}`);
  };

  return (
    <TooltipProvider>
      <Card
        className="bg-slate-800 border-slate-700 hover:border-slate-600 transition-all cursor-pointer group"
        onClick={handleClick}
      >
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            {/* Status Icon */}
            <div
              className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${
                (status === 'streaming' || status === 'running') ? 'bg-blue-500/20' : 'bg-slate-700'
              }`}
            >
              <StatusIcon
                className={`h-5 w-5 ${statusConfig.iconColor} ${
                  (status === 'streaming' || status === 'running') ? 'animate-spin' : ''
                }`}
              />
            </div>

            {/* Main Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  {/* Query */}
                  <div className="flex items-center gap-2 mb-1">
                    <Search className="h-4 w-4 text-slate-500 flex-shrink-0" />
                    <h3 className="text-slate-100 font-medium truncate group-hover:text-blue-400 transition-colors">
                      {query}
                    </h3>
                  </div>

                  {/* Meta Info */}
                  <div className="flex items-center gap-4 text-sm text-slate-400">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      <span>{formatRelativeTime(created_at)}</span>
                    </div>
                    {duration_ms !== undefined && (
                      <div className="flex items-center gap-1">
                        <span>Duration: {formatDuration(duration_ms)}</span>
                      </div>
                    )}
                    {entity_count !== undefined && entity_count > 0 && (
                      <div className="flex items-center gap-1">
                        <Wrench className="h-3.5 w-3.5" />
                        <span>{entity_count} entities</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Status Badge */}
                <Badge className={`flex-shrink-0 ${statusConfig.color}`}>
                  {statusConfig.label}
                </Badge>
              </div>

              {/* Actions (shown on hover) */}
              <div className="flex items-center gap-2 mt-3 opacity-0 group-hover:opacity-100 transition-opacity">
                {status === 'completed' && (
                  <>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleViewGraph}
                          className="h-8 border-slate-600 text-slate-300 hover:bg-slate-700"
                        >
                          <Network className="h-3.5 w-3.5 mr-1.5" />
                          Graph
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>View threat graph</TooltipContent>
                    </Tooltip>

                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleCreateReport}
                          className="h-8 border-slate-600 text-slate-300 hover:bg-slate-700"
                        >
                          <FileText className="h-3.5 w-3.5 mr-1.5" />
                          Report
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Create report</TooltipContent>
                    </Tooltip>
                  </>
                )}

                <div className="flex-1" />

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-slate-400 hover:text-white"
                >
                  View Details
                  <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}
