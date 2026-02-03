"""Graph service for entity extraction and relationship inference."""
import re
from typing import Optional
from uuid import UUID

from ..models.graph import GraphNode, GraphEdge, GraphData


class GraphService:
    """
    Extracts entities and relationships from investigation results.

    Parses IOCs, threat actors, malware, and other entities from
    investigation text and sub-agent results.
    """

    # Regex patterns for IOC extraction
    IOC_PATTERNS = {
        "ioc_ip": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "ioc_domain": r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:onion|com|net|org|io|ru|cn)\b",
        "ioc_hash_md5": r"\b[a-fA-F0-9]{32}\b",
        "ioc_hash_sha1": r"\b[a-fA-F0-9]{40}\b",
        "ioc_hash_sha256": r"\b[a-fA-F0-9]{64}\b",
        "ioc_email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "ioc_btc": r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",
        "ioc_eth": r"\b0x[a-fA-F0-9]{40}\b",
        "ioc_xmr": r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b",
        "cve": r"CVE-\d{4}-\d{4,7}",
    }

    # Common threat actor keywords
    THREAT_ACTOR_KEYWORDS = [
        "APT", "threat actor", "group", "gang", "ransomware group",
        "hacker", "operator", "affiliate",
    ]

    # Malware family patterns
    MALWARE_KEYWORDS = [
        "malware", "ransomware", "trojan", "RAT", "stealer",
        "loader", "botnet", "backdoor", "exploit", "kit",
    ]

    def extract_from_investigation(
        self,
        investigation_id: UUID,
        result_text: str,
        subagent_results: list[dict],
    ) -> GraphData:
        """
        Extract graph data from investigation results.

        Args:
            investigation_id: The investigation ID
            result_text: Full investigation response text
            subagent_results: Results from sub-agents

        Returns:
            GraphData with nodes and edges
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        seen_node_ids: set[str] = set()

        # Extract IOCs from text
        for ioc_type, pattern in self.IOC_PATTERNS.items():
            matches = re.findall(pattern, result_text, re.IGNORECASE)
            for match in set(matches):
                node_id = f"{ioc_type}:{match.lower()}"
                if node_id not in seen_node_ids:
                    seen_node_ids.add(node_id)
                    # Normalize hash types
                    display_type = ioc_type
                    if ioc_type.startswith("ioc_hash_"):
                        display_type = "ioc_hash"
                    nodes.append(GraphNode(
                        id=node_id,
                        type=display_type,
                        label=match,
                        investigation_ids=[str(investigation_id)],
                    ))

        # Process sub-agent results for structured entities
        for sa_result in subagent_results:
            if not sa_result.get("success"):
                continue

            agent_type = sa_result.get("agent_type", "")
            analysis = sa_result.get("analysis", "")

            if agent_type == "ThreatActorProfiler":
                actor_nodes = self._extract_threat_actors(
                    analysis, str(investigation_id)
                )
                for node in actor_nodes:
                    if node.id not in seen_node_ids:
                        seen_node_ids.add(node.id)
                        nodes.append(node)

            elif agent_type == "MalwareAnalyst":
                malware_nodes = self._extract_malware(
                    analysis, str(investigation_id)
                )
                for node in malware_nodes:
                    if node.id not in seen_node_ids:
                        seen_node_ids.add(node.id)
                        nodes.append(node)

            elif agent_type == "MarketplaceInvestigator":
                market_nodes = self._extract_marketplaces(
                    analysis, str(investigation_id)
                )
                for node in market_nodes:
                    if node.id not in seen_node_ids:
                        seen_node_ids.add(node.id)
                        nodes.append(node)

        # Infer relationships based on co-occurrence
        edges = self._infer_relationships(nodes, result_text)

        return GraphData(nodes=nodes, edges=edges)

    def _extract_threat_actors(
        self,
        analysis: str,
        investigation_id: str,
    ) -> list[GraphNode]:
        """Extract threat actor entities from profiler analysis."""
        nodes = []

        # Look for "Threat Actor Profile: NAME" pattern
        profile_match = re.search(
            r"Threat Actor Profile:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if profile_match:
            name = profile_match.group(1).strip()
            nodes.append(GraphNode(
                id=f"threat_actor:{name.lower().replace(' ', '_')}",
                type="threat_actor",
                label=name,
                investigation_ids=[investigation_id],
                confidence="high",
            ))

        # Look for aliases
        aliases_match = re.search(
            r"Aliases?:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if aliases_match:
            aliases = aliases_match.group(1).strip()
            for alias in re.split(r"[,;]", aliases):
                alias = alias.strip()
                if alias and len(alias) > 2:
                    nodes.append(GraphNode(
                        id=f"threat_actor:{alias.lower().replace(' ', '_')}",
                        type="threat_actor",
                        label=alias,
                        investigation_ids=[investigation_id],
                        confidence="medium",
                    ))

        return nodes

    def _extract_malware(
        self,
        analysis: str,
        investigation_id: str,
    ) -> list[GraphNode]:
        """Extract malware entities from analyst results."""
        nodes = []

        # Look for "Malware Analysis: NAME" pattern
        malware_match = re.search(
            r"Malware Analysis:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if malware_match:
            name = malware_match.group(1).strip()
            nodes.append(GraphNode(
                id=f"malware:{name.lower().replace(' ', '_')}",
                type="malware",
                label=name,
                investigation_ids=[investigation_id],
                confidence="high",
            ))

        # Look for malware family mentions
        family_match = re.search(
            r"Family:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if family_match:
            family = family_match.group(1).strip()
            if family and len(family) > 2:
                nodes.append(GraphNode(
                    id=f"malware:{family.lower().replace(' ', '_')}",
                    type="malware",
                    label=family,
                    investigation_ids=[investigation_id],
                    confidence="high",
                ))

        return nodes

    def _extract_marketplaces(
        self,
        analysis: str,
        investigation_id: str,
    ) -> list[GraphNode]:
        """Extract marketplace entities from investigator results."""
        nodes = []

        # Look for "Marketplace Analysis: NAME" pattern
        market_match = re.search(
            r"Marketplace Analysis:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if market_match:
            name = market_match.group(1).strip()
            nodes.append(GraphNode(
                id=f"marketplace:{name.lower().replace(' ', '_')}",
                type="marketplace",
                label=name,
                investigation_ids=[investigation_id],
                confidence="high",
            ))

        # Look for vendor profiles
        vendor_match = re.search(
            r"Vendor Profile:\s*([^\n]+)",
            analysis,
            re.IGNORECASE,
        )
        if vendor_match:
            vendor = vendor_match.group(1).strip()
            nodes.append(GraphNode(
                id=f"vendor:{vendor.lower().replace(' ', '_')}",
                type="vendor",
                label=vendor,
                investigation_ids=[investigation_id],
                confidence="medium",
            ))

        return nodes

    def _infer_relationships(
        self,
        nodes: list[GraphNode],
        text: str,
    ) -> list[GraphEdge]:
        """
        Infer relationships between nodes based on text analysis.

        Uses simple co-occurrence and context clues.
        """
        edges = []
        edge_id = 0

        # Group nodes by type
        threat_actors = [n for n in nodes if n.type == "threat_actor"]
        malware = [n for n in nodes if n.type == "malware"]
        iocs = [n for n in nodes if n.type.startswith("ioc_")]
        markets = [n for n in nodes if n.type == "marketplace"]
        vendors = [n for n in nodes if n.type == "vendor"]
        cves = [n for n in nodes if n.type == "cve"]

        # Threat actor -> malware (uses)
        for actor in threat_actors:
            for mal in malware:
                if self._mentioned_together(actor.label, mal.label, text):
                    edge_id += 1
                    edges.append(GraphEdge(
                        id=f"edge:{edge_id}",
                        source=actor.id,
                        target=mal.id,
                        type="uses",
                        weight=2,
                    ))

        # Threat actor -> IOC (associated_with)
        for actor in threat_actors:
            for ioc in iocs:
                if self._mentioned_together(actor.label, ioc.label, text, window=500):
                    edge_id += 1
                    edges.append(GraphEdge(
                        id=f"edge:{edge_id}",
                        source=actor.id,
                        target=ioc.id,
                        type="associated_with",
                        weight=1,
                    ))

        # Malware -> CVE (exploits)
        for mal in malware:
            for cve in cves:
                if self._mentioned_together(mal.label, cve.label, text):
                    edge_id += 1
                    edges.append(GraphEdge(
                        id=f"edge:{edge_id}",
                        source=mal.id,
                        target=cve.id,
                        type="exploits",
                        weight=2,
                    ))

        # Vendor -> Marketplace (sells_on)
        for vendor in vendors:
            for market in markets:
                edge_id += 1
                edges.append(GraphEdge(
                    id=f"edge:{edge_id}",
                    source=vendor.id,
                    target=market.id,
                    type="sells_on",
                    weight=1,
                ))

        return edges

    def _mentioned_together(
        self,
        term1: str,
        term2: str,
        text: str,
        window: int = 200,
    ) -> bool:
        """Check if two terms appear within a text window."""
        text_lower = text.lower()
        term1_lower = term1.lower()
        term2_lower = term2.lower()

        # Find all positions of term1
        pos1 = [m.start() for m in re.finditer(re.escape(term1_lower), text_lower)]

        # Find all positions of term2
        pos2 = [m.start() for m in re.finditer(re.escape(term2_lower), text_lower)]

        # Check if any positions are within window
        for p1 in pos1:
            for p2 in pos2:
                if abs(p1 - p2) <= window:
                    return True

        return False

    def merge_graphs(self, graphs: list[GraphData]) -> GraphData:
        """
        Merge multiple graphs into one.

        Deduplicates nodes and combines investigation_ids.
        """
        merged_nodes: dict[str, GraphNode] = {}
        merged_edges: dict[str, GraphEdge] = {}

        for graph in graphs:
            for node in graph.nodes:
                if node.id in merged_nodes:
                    # Merge investigation_ids
                    existing = merged_nodes[node.id]
                    existing.investigation_ids = list(set(
                        existing.investigation_ids + node.investigation_ids
                    ))
                else:
                    merged_nodes[node.id] = node

            for edge in graph.edges:
                edge_key = f"{edge.source}:{edge.target}:{edge.type}"
                if edge_key in merged_edges:
                    # Increase weight for repeated edges
                    merged_edges[edge_key].weight += 1
                else:
                    merged_edges[edge_key] = edge

        return GraphData(
            nodes=list(merged_nodes.values()),
            edges=list(merged_edges.values()),
        )
