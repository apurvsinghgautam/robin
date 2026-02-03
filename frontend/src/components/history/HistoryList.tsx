'use client';

import React from 'react';
import { History, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import HistoryCard from './HistoryCard';
import { InvestigationSummary } from '@/types';

interface HistoryListProps {
  investigations: InvestigationSummary[];
  loading: boolean;
  error: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
}

export default function HistoryList({
  investigations,
  loading,
  error,
  hasMore,
  loadingMore,
  onLoadMore,
  onRetry,
}: HistoryListProps) {
  // Loading state
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="bg-slate-800 rounded-lg border border-slate-700 p-4 animate-pulse"
          >
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 bg-slate-700 rounded-lg" />
              <div className="flex-1">
                <div className="h-5 bg-slate-700 rounded w-2/3 mb-2" />
                <div className="h-4 bg-slate-700 rounded w-1/3" />
              </div>
              <div className="w-20 h-6 bg-slate-700 rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-3" />
        <p className="text-red-400 mb-4">{error}</p>
        <Button onClick={onRetry} variant="outline" className="border-slate-700">
          Try Again
        </Button>
      </div>
    );
  }

  // Empty state
  if (investigations.length === 0) {
    return (
      <div className="text-center py-12">
        <History className="h-12 w-12 text-slate-600 mx-auto mb-3" />
        <p className="text-slate-400 mb-2">No investigations found</p>
        <p className="text-sm text-slate-500">
          Try adjusting your filters or start a new investigation
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Investigation Cards */}
      {investigations.map((investigation) => (
        <HistoryCard
          key={investigation.id}
          id={investigation.id}
          query={investigation.initial_query || investigation.query || ''}
          status={investigation.status}
          created_at={investigation.created_at}
          duration_ms={investigation.duration_ms}
          entity_count={investigation.entity_count}
        />
      ))}

      {/* Load More */}
      {hasMore && (
        <div className="flex justify-center pt-4">
          <Button
            variant="outline"
            onClick={onLoadMore}
            disabled={loadingMore}
            className="border-slate-700 text-slate-300 hover:bg-slate-800"
          >
            {loadingMore ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Loading...
              </>
            ) : (
              'Load More'
            )}
          </Button>
        </div>
      )}
    </div>
  );
}
