'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  ArrowRight,
  Loader2,
  Lightbulb,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useInvestigationStore } from '@/stores/investigationStore';

// ============================================
// Example Queries
// ============================================

const exampleQueries = [
  'Research the LockBit ransomware group and their recent activities',
  'Investigate cryptocurrency wallets associated with darknet markets',
  'Find information about the Genesis Market takedown',
  'Analyze the ALPHV/BlackCat ransomware ecosystem',
  'Research recent data breaches in the healthcare sector',
  'Investigate phishing infrastructure targeting financial institutions',
];

// ============================================
// New Investigation Page
// ============================================

export default function NewInvestigationPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startInvestigation = useInvestigationStore((s) => s.startInvestigation);

  const handleStart = async (investigationQuery: string) => {
    if (!investigationQuery.trim() || isStarting) return;

    setIsStarting(true);
    setError(null);

    try {
      const investigationId = await startInvestigation(investigationQuery.trim());
      router.push(`/investigations/${investigationId}`);
    } catch (err) {
      console.error('Failed to start investigation:', err);
      setError(
        err instanceof Error ? err.message : 'Failed to start investigation'
      );
      setIsStarting(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleStart(query);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-6">
      <div className="w-full max-w-3xl">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">New Investigation</h1>
          <p className="text-muted-foreground">
            Describe what you want to research and our AI agents will investigate
          </p>
        </div>

        {/* Query Input */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="relative">
            <textarea
              placeholder="What would you like to investigate? Be specific about threat actors, malware, IOCs, or other topics..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full min-h-[120px] p-4 rounded-lg border border-input bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              disabled={isStarting}
            />
            <div className="absolute bottom-4 right-4 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">
                {query.length}/500
              </span>
            </div>
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full mt-4"
            disabled={!query.trim() || isStarting || query.length > 500}
          >
            {isStarting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Starting Investigation...
              </>
            ) : (
              <>
                <Search className="h-4 w-4 mr-2" />
                Start Investigation
                <ArrowRight className="h-4 w-4 ml-2" />
              </>
            )}
          </Button>
        </form>

        {/* Example Queries */}
        <div>
          <div className="flex items-center gap-2 mb-4 text-sm text-muted-foreground">
            <Lightbulb className="h-4 w-4" />
            <span>Try one of these examples:</span>
          </div>
          <div className="grid gap-2">
            {exampleQueries.map((exampleQuery, index) => (
              <Card
                key={index}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => !isStarting && setQuery(exampleQuery)}
              >
                <CardContent className="p-3 flex items-center justify-between">
                  <span className="text-sm">{exampleQuery}</span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground flex-shrink-0 ml-2" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Tips */}
        <div className="mt-8 p-4 rounded-lg bg-muted/50 text-sm">
          <h3 className="font-medium mb-2">Tips for effective investigations:</h3>
          <ul className="space-y-1 text-muted-foreground list-disc list-inside">
            <li>Be specific about threat actors, malware families, or IOCs</li>
            <li>Include time frames if relevant (e.g., "activities in 2024")</li>
            <li>Ask for specific types of analysis (TTPs, infrastructure, victims)</li>
            <li>You can ask follow-up questions during the investigation</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
