// Graph-specific types for Robin OSINT platform
// Note: This extends the core types from index.ts with visualization-specific types

import { EntityType, Entity, GraphNode as BaseGraphNode, GraphEdge as BaseGraphEdge } from './index';

// Extended GraphNode type for visualization with styling
export interface GraphNode {
  id: string;
  type: 'threat_actor' | 'malware' | 'ioc_ip' | 'ioc_domain' | 'ioc_hash' | 'ioc_email' | 'marketplace' | 'vendor' | 'cve';
  label: string;
  properties: Record<string, any>;
  confidence: 'high' | 'medium' | 'low';
}

// Extended GraphEdge type for visualization
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'uses' | 'targets' | 'associated_with' | 'communicates_with' | 'sells_on' | 'exploits';
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// Investigation types compatible with API
export interface InvestigationSummary {
  id: string;
  query: string;
  status: 'completed' | 'failed' | 'running';
  createdAt: string;
  duration_ms?: number;
  toolsUsed: number;
  nodeCount?: number;
  edgeCount?: number;
}

// Report types
export interface Report {
  id: string;
  title: string;
  investigationId: string;
  sections: ReportSection[];
  createdAt: string;
  updatedAt: string;
  status: 'draft' | 'published';
}

export interface ReportSection {
  id: string;
  type: 'summary' | 'text' | 'ioc_table' | 'analysis';
  title: string;
  content: string;
  order: number;
}

export interface IOCEntry {
  type: 'ip' | 'domain' | 'hash' | 'email' | 'url';
  value: string;
  context: string;
  confidence: 'high' | 'medium' | 'low';
}

// Node styling configuration
export const NODE_STYLES: Record<GraphNode['type'], { color: string; shape: string; label: string }> = {
  threat_actor: { color: '#ef4444', shape: 'diamond', label: 'Threat Actor' },
  malware: { color: '#f97316', shape: 'hexagon', label: 'Malware' },
  ioc_ip: { color: '#3b82f6', shape: 'ellipse', label: 'IP Address' },
  ioc_domain: { color: '#3b82f6', shape: 'ellipse', label: 'Domain' },
  ioc_hash: { color: '#3b82f6', shape: 'ellipse', label: 'Hash' },
  ioc_email: { color: '#3b82f6', shape: 'ellipse', label: 'Email' },
  marketplace: { color: '#8b5cf6', shape: 'rectangle', label: 'Marketplace' },
  vendor: { color: '#a78bfa', shape: 'rectangle', label: 'Vendor' },
  cve: { color: '#eab308', shape: 'ellipse', label: 'CVE' },
};

export const EDGE_STYLES: Record<GraphEdge['type'], { color: string; label: string }> = {
  uses: { color: '#64748b', label: 'Uses' },
  targets: { color: '#ef4444', label: 'Targets' },
  associated_with: { color: '#3b82f6', label: 'Associated With' },
  communicates_with: { color: '#10b981', label: 'Communicates With' },
  sells_on: { color: '#8b5cf6', label: 'Sells On' },
  exploits: { color: '#f97316', label: 'Exploits' },
};

export const CONFIDENCE_COLORS: Record<GraphNode['confidence'], string> = {
  high: '#22c55e',
  medium: '#eab308',
  low: '#ef4444',
};

// Utility function to convert API types to visualization types
export function convertToVisualizationNode(entity: Entity): GraphNode {
  const typeMap: Record<EntityType, GraphNode['type']> = {
    threat_actor: 'threat_actor',
    malware: 'malware',
    ioc: 'ioc_hash',
    marketplace: 'marketplace',
    vulnerability: 'cve',
    infrastructure: 'ioc_ip',
    person: 'vendor',
    organization: 'vendor',
    crypto_wallet: 'ioc_hash',
    domain: 'ioc_domain',
    ip_address: 'ioc_ip',
    email: 'ioc_email',
    unknown: 'ioc_hash',
  };

  return {
    id: entity.id,
    type: typeMap[entity.type] || 'ioc_hash',
    label: entity.name,
    properties: entity.attributes,
    confidence: entity.confidence
      ? entity.confidence >= 0.8 ? 'high'
        : entity.confidence >= 0.5 ? 'medium'
        : 'low'
      : 'medium',
  };
}
