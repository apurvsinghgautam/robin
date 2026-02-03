"""Graph-related Pydantic models."""
from typing import Any, Optional
from pydantic import BaseModel


class GraphNode(BaseModel):
    """Node in the threat intelligence graph."""
    id: str
    type: str  # threat_actor, ioc_ip, ioc_domain, ioc_hash, malware, marketplace, cve
    label: str
    properties: dict[str, Any] = {}
    confidence: str = "medium"  # high, medium, low
    investigation_ids: list[str] = []
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class GraphEdge(BaseModel):
    """Edge in the threat intelligence graph."""
    id: str
    source: str
    target: str
    type: str  # uses, targets, associated_with, communicates_with, sells_on, exploits
    properties: dict[str, Any] = {}
    weight: int = 1


class GraphData(BaseModel):
    """Complete graph data for visualization."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
