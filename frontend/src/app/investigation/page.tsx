"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useInvestigationStore } from "@/stores/investigationStore";

const EXAMPLE_QUERIES = [
  "Find recent ransomware payment addresses associated with LockBit",
  "Investigate threat actor selling corporate VPN access",
  "Search for leaked credentials from healthcare sector",
  "Analyze malware samples distributed via Telegram channels",
  "Track cryptocurrency transactions linked to darknet markets",
];

export default function InvestigationPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { startInvestigation } = useInvestigationStore();

  const handleSubmit = async (submittedQuery: string) => {
    if (!submittedQuery.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const investigationId = await startInvestigation(submittedQuery.trim());
      router.push(`/investigation/${investigationId}`);
    } catch (error) {
      console.error("Failed to start investigation:", error);
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(query);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-3xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center gap-3">
            <div className="p-3 rounded-full bg-primary/10">
              <Search className="h-8 w-8 text-primary" />
            </div>
          </div>
          <h1 className="text-4xl font-bold tracking-tight">
            Dark Web Investigation
          </h1>
          <p className="text-muted-foreground text-lg">
            Enter your OSINT query to begin investigating the dark web
          </p>
        </div>

        {/* Main Input */}
        <Card className="p-6 bg-card/50 backdrop-blur border-border/50">
          <div className="space-y-4">
            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe what you want to investigate..."
                className="w-full min-h-[120px] p-4 bg-background border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 text-foreground placeholder:text-muted-foreground"
                disabled={isSubmitting}
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                Press{" "}
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">
                  Cmd
                </kbd>{" "}
                +{" "}
                <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">
                  Enter
                </kbd>{" "}
                to submit
              </span>
              <Button
                onClick={() => handleSubmit(query)}
                disabled={!query.trim() || isSubmitting}
                size="lg"
                className="gap-2"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    Start Investigation
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>

        {/* Example Queries */}
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground text-center">
            Example queries
          </h2>
          <div className="flex flex-wrap gap-2 justify-center">
            {EXAMPLE_QUERIES.map((exampleQuery, index) => (
              <button
                key={index}
                onClick={() => setQuery(exampleQuery)}
                disabled={isSubmitting}
                className="px-3 py-2 text-sm bg-muted/50 hover:bg-muted rounded-lg transition-colors text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed text-left"
              >
                {exampleQuery}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
