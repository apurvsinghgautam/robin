'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Search,
  ArrowRight,
  Clock,
  Network,
  FileText,
  Shield,
  TrendingUp,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { investigationAPI } from '@/lib/api';
import { useInvestigationStore } from '@/stores/investigationStore';
import { formatRelativeTime, truncate } from '@/lib/utils';
import type { InvestigationSummary } from '@/types';

// ============================================
// Dashboard Page
// ============================================

export default function DashboardPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const startInvestigation = useInvestigationStore((s) => s.startInvestigation);

  // Fetch recent investigations
  const {
    data: recentData,
    isLoading: isLoadingRecent,
    error: recentError,
  } = useQuery({
    queryKey: ['investigations', 'recent'],
    queryFn: () => investigationAPI.list(1, 5),
  });

  const handleStartInvestigation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || isStarting) return;

    setIsStarting(true);
    try {
      const investigationId = await startInvestigation(query.trim());
      router.push(`/investigations/${investigationId}`);
    } catch (error) {
      console.error('Failed to start investigation:', error);
      setIsStarting(false);
    }
  };

  return (
    <div className="min-h-screen p-6 md:p-8 lg:p-10">
      {/* Hero Section */}
      <div className="max-w-4xl mx-auto text-center mb-12">
        <div className="flex items-center justify-center gap-3 mb-4">
          <Shield className="h-12 w-12 text-primary" />
          <h1 className="text-4xl md:text-5xl font-bold gradient-text">
            Robin
          </h1>
        </div>
        <p className="text-lg text-muted-foreground mb-8">
          Dark Web OSINT Research Platform
        </p>

        {/* Search Form */}
        <form onSubmit={handleStartInvestigation} className="flex gap-2 max-w-2xl mx-auto">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Start a new investigation... (e.g., 'Research threat actor LockBit')"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-10 h-12 bg-card border-border"
              disabled={isStarting}
            />
          </div>
          <Button
            type="submit"
            size="lg"
            className="h-12 px-6"
            disabled={!query.trim() || isStarting}
          >
            {isStarting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                Investigate
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </form>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto mb-12">
        <Link href="/investigations/new">
          <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
            <CardContent className="flex items-center gap-4 p-4">
              <div className="p-2 rounded-lg bg-primary/10">
                <Search className="h-5 w-5 text-primary" />
              </div>
              <div>
                <h3 className="font-medium">New Investigation</h3>
                <p className="text-sm text-muted-foreground">
                  Start researching a topic
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link href="/graph">
          <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
            <CardContent className="flex items-center gap-4 p-4">
              <div className="p-2 rounded-lg bg-blue-500/10">
                <Network className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <h3 className="font-medium">Entity Graph</h3>
                <p className="text-sm text-muted-foreground">
                  Visualize relationships
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>

        <Link href="/reports">
          <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
            <CardContent className="flex items-center gap-4 p-4">
              <div className="p-2 rounded-lg bg-violet-500/10">
                <FileText className="h-5 w-5 text-violet-400" />
              </div>
              <div>
                <h3 className="font-medium">Reports</h3>
                <p className="text-sm text-muted-foreground">
                  Generate intelligence reports
                </p>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Recent Investigations */}
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" />
            Recent Investigations
          </h2>
          <Link href="/history">
            <Button variant="ghost" size="sm">
              View all
              <ArrowRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>

        {isLoadingRecent ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
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
        ) : recentError ? (
          <Card>
            <CardContent className="p-6 text-center">
              <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
              <p className="text-muted-foreground">
                Failed to load recent investigations
              </p>
            </CardContent>
          </Card>
        ) : recentData?.investigations?.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center">
              <TrendingUp className="h-12 w-12 text-muted-foreground/50 mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No investigations yet</h3>
              <p className="text-muted-foreground mb-4">
                Start your first investigation to begin researching threats
              </p>
              <Link href="/investigations/new">
                <Button>
                  <Search className="h-4 w-4 mr-2" />
                  Start Investigating
                </Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {recentData?.investigations?.map((investigation: InvestigationSummary) => (
              <Link
                key={investigation.id}
                href={`/investigations/${investigation.id}`}
              >
                <Card className="hover:bg-accent/50 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-medium truncate">
                          {truncate(investigation.initial_query || investigation.query || '', 80)}
                        </h3>
                        <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                          <span>{formatRelativeTime(investigation.created_at)}</span>
                          {investigation.entity_count && investigation.entity_count > 0 && (
                            <span className="flex items-center gap-1">
                              <Network className="h-3.5 w-3.5" />
                              {investigation.entity_count} entities
                            </span>
                          )}
                        </div>
                      </div>
                      <StatusBadge status={investigation.status} />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// Status Badge Component
// ============================================

function StatusBadge({ status }: { status: InvestigationSummary['status'] }) {
  const variants: Record<
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

  const { variant, label } = variants[status] || variants.pending;

  return (
    <Badge variant={variant} className="shrink-0">
      {(status === 'streaming' || status === 'running') && (
        <span className="w-2 h-2 rounded-full bg-primary animate-pulse mr-1.5" />
      )}
      {label}
    </Badge>
  );
}
