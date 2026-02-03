'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  Plus,
  Clock,
  Network,
  Filter,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { investigationAPI } from '@/lib/api';
import { formatRelativeTime, truncate } from '@/lib/utils';
import type { InvestigationSummary } from '@/types';

// ============================================
// Investigations List Page
// ============================================

export default function InvestigationsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['investigations', page, pageSize],
    queryFn: () => investigationAPI.list(page, pageSize),
  });

  const filteredInvestigations = data?.investigations?.filter((inv) =>
    (inv.initial_query || inv.query || '').toLowerCase().includes(searchQuery.toLowerCase())
  ) || [];

  return (
    <div className="p-6 md:p-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Investigations</h1>
          <p className="text-muted-foreground">
            Manage and review your research investigations
          </p>
        </div>
        <Link href="/investigations/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Investigation
          </Button>
        </Link>
      </div>

      {/* Search and Filters */}
      <div className="flex gap-3 mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search investigations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button variant="outline" size="icon">
          <Filter className="h-4 w-4" />
        </Button>
      </div>

      {/* Investigations List */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="space-y-2 flex-1">
                    <Skeleton className="h-5 w-3/4" />
                    <Skeleton className="h-4 w-1/4" />
                  </div>
                  <Skeleton className="h-6 w-20" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Card>
          <CardContent className="p-6 text-center">
            <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
            <p className="text-muted-foreground mb-4">
              Failed to load investigations
            </p>
            <Button onClick={() => refetch()} variant="outline">
              Try Again
            </Button>
          </CardContent>
        </Card>
      ) : filteredInvestigations.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Search className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">
              {searchQuery ? 'No matching investigations' : 'No investigations yet'}
            </h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery
                ? 'Try a different search term'
                : 'Start your first investigation to begin researching threats'}
            </p>
            {!searchQuery && (
              <Link href="/investigations/new">
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Start Investigating
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="space-y-3">
            {filteredInvestigations.map((investigation) => (
              <InvestigationCard key={investigation.id} investigation={investigation} />
            ))}
          </div>

          {/* Pagination */}
          {data && data.total > pageSize && (
            <div className="flex items-center justify-center gap-2 mt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {Math.ceil(data.total / pageSize)}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(data.total / pageSize)}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ============================================
// Investigation Card Component
// ============================================

function InvestigationCard({ investigation }: { investigation: InvestigationSummary }) {
  return (
    <Link href={`/investigations/${investigation.id}`}>
      <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h3 className="font-medium truncate">
                {truncate(investigation.initial_query || investigation.query || '', 100)}
              </h3>
              <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {formatRelativeTime(investigation.created_at)}
                </span>
                {investigation.entity_count && investigation.entity_count > 0 && (
                  <span className="flex items-center gap-1">
                    <Network className="h-3.5 w-3.5" />
                    {investigation.entity_count} entities
                  </span>
                )}
                {investigation.duration_ms && (
                  <span>
                    {(investigation.duration_ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>
            </div>
            <StatusBadge status={investigation.status} />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

// ============================================
// Status Badge Component
// ============================================

function StatusBadge({ status }: { status: InvestigationSummary['status'] }) {
  const config: Record<
    InvestigationSummary['status'],
    { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }
  > = {
    pending: { variant: 'secondary', label: 'Pending' },
    streaming: { variant: 'default', label: 'Running' },
    running: { variant: 'default', label: 'Running' },
    completed: { variant: 'outline', label: 'Completed' },
    error: { variant: 'destructive', label: 'Error' },
    failed: { variant: 'destructive', label: 'Failed' },
  };

  const { variant, label } = config[status] || config.pending;

  return (
    <Badge variant={variant} className="shrink-0">
      {(status === 'streaming' || status === 'running') && (
        <Loader2 className="h-3 w-3 animate-spin mr-1" />
      )}
      {label}
    </Badge>
  );
}
