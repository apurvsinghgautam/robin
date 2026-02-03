"use client";

import { SubAgentBadge, AgentType, AgentStatus } from "./SubAgentBadge";
import { SubAgentResult } from "@/types";

interface SubAgentResultsProps {
  results: SubAgentResult[];
}

// Map API agent_type to AgentType
function mapAgentType(agentType: string): AgentType {
  const mapping: Record<string, AgentType> = {
    'threat_actor_profiler': 'ThreatActorProfiler',
    'ioc_extractor': 'IOCExtractor',
    'malware_analyst': 'MalwareAnalyst',
    'marketplace_investigator': 'MarketplaceInvestigator',
  };
  return mapping[agentType] || 'ThreatActorProfiler';
}

export function SubAgentResults({ results }: SubAgentResultsProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-4">
        <p className="text-sm text-muted-foreground">No sub-agent analysis yet</p>
      </div>
    );
  }

  // Sort by started_at, most recent first
  const sortedResults = [...results].sort(
    (a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
  );

  return (
    <div className="space-y-2">
      {sortedResults.map((result, index) => (
        <SubAgentBadge
          key={`${result.agent_type}-${index}`}
          agentType={mapAgentType(result.agent_type)}
          status={result.success ? 'completed' : (result.completed_at ? 'failed' : 'running')}
          analysis={result.analysis}
        />
      ))}
    </div>
  );
}
