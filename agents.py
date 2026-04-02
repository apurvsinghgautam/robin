"""
Multi-Agent System for Dark Web Threat Intelligence

Loads agent personalities, roles, and behaviors from the Agents folder.
Provides foundational Agent class and context management.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import re

AGENTS_DIR = Path("Agents/Investigation Division")


@dataclass
class AgentContext:
    """Shared context passed between agents during investigation."""
    query: str
    raw_data: str  # Scraped content from dark web
    artifacts_found: Dict = None  # IOCs, entities, wallets, etc.
    timeline_events: List = None  # Temporal events
    threat_actors: List = None  # Identified actor profiles
    attribution_chain: List = None  # Attribution evidence
    investigation_stage: str = "discovery"
    agent_contributions: Dict = None  # Track which agent produced what
    confidence_scores: Dict = None  # Confidence per finding
    
    def __post_init__(self):
        if self.artifacts_found is None:
            self.artifacts_found = {}
        if self.timeline_events is None:
            self.timeline_events = []
        if self.threat_actors is None:
            self.threat_actors = []
        if self.attribution_chain is None:
            self.attribution_chain = []
        if self.agent_contributions is None:
            self.agent_contributions = {}
        if self.confidence_scores is None:
            self.confidence_scores = {}


class Agent:
    """Base Agent class. Each agent has personality, role, and behavior."""
    
    def __init__(self, name: str, personality: str, role: str, behavior: str):
        self.name = name
        self.personality = personality
        self.role = role
        self.behavior = behavior
        self.findings = {}
        self.confidence = 0.0
        
    def get_system_prompt(self) -> str:
        """Build system prompt from personality + role + behavior."""
        return f"""You are {self.name}.

PERSONALITY:
{self.personality}

ROLE:
{self.role}

BEHAVIOR:
{self.behavior}

You are part of a multi-agent threat investigation team. Stay focused on your role.
Reference your context carefully. Never speculate beyond your expertise.
Always specify confidence levels for claims (High/Medium/Low).
"""
    
    async def analyze(self, llm, context: AgentContext) -> Dict:
        """Override in subclasses. Runs this agent's analysis."""
        raise NotImplementedError
    
    def to_dict(self) -> dict:
        """Export agent findings."""
        return {
            "name": self.name,
            "findings": self.findings,
            "confidence": self.confidence,
        }


def load_agent(agent_name: str) -> Optional[Agent]:
    """Load an agent from the Agents folder."""
    agent_file = AGENTS_DIR / agent_name
    if not agent_file.exists():
        return None
    
    content = agent_file.read_text()
    
    personality = extract_section(content, "PERSONALITY:")
    role = extract_section(content, "ROLE:")
    behavior = extract_section(content, "BEHAVIOR:")
    
    return Agent(agent_name, personality, role, behavior)


def extract_section(text: str, header: str) -> str:
    """Extract a section from agent profile file."""
    pattern = rf"{re.escape(header)}(.*?)(?=\n[A-Z][A-Z0-9\s-]+:|$)"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def load_all_agents() -> Dict[str, Agent]:
    """Load all available agents."""
    agents = {}
    if not AGENTS_DIR.exists():
        return agents
    
    for agent_file in AGENTS_DIR.iterdir():
        if agent_file.is_file():
            agent_name = agent_file.name
            agent = load_agent(agent_name)
            if agent:
                agents[agent_name] = agent
    
    return agents


# Commonly used agent name shortcuts
AGENT_ROSTER = {
    "REAPER": "REAPER — Threat Hunter",
    "TRACE": "TRACE — Digital Forensics Investigator",
    "BISHOP": "BISHOP — Attribution Analyst",
    "LEDGER": "LEDGER — Blockchain Investigator",
    "MASON": "MASON — Incident Response Investigator",
    "FLUX": "FLUX — Log & Timeline Expert",
    "VEIL": "VEIL — Dark Web Researcher",
    "ARCHIVIST": "ARCHIVIST — Data Recovery Specialist",
    "PRISM": "PRISM — Traffic & Protocol Analyst",
    "GHOST": "GHOST — Undercover Intelligence Researcher",
}


def get_agent(short_name: str) -> Optional[Agent]:
    """Get agent by short name (e.g., 'REAPER' -> 'REAPER — Threat Hunter')."""
    full_name = AGENT_ROSTER.get(short_name.upper())
    if full_name:
        return load_agent(full_name)
    return None


def list_available_agents() -> List[str]:
    """List all available agent short names."""
    return list(AGENT_ROSTER.keys())
