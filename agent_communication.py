"""
Enhanced Multi-Agent Communication System

All 24+ agents with inter-agent messaging and collaboration.
Agents can query, learn from, and collaborate with each other.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import re
from collections import defaultdict

AGENTS_ROOT = Path("Agents")
SUPPORTED_AGENT_EXTENSIONS = {".md", ".markdown", ".txt"}


@dataclass
class AgentMessage:
    """Message passed between agents."""
    sender: str
    recipient: str
    message_type: str  # "query", "response", "finding", "alert", "coordination"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    context_id: str = ""  # Links messages to same investigation


@dataclass
class AgentContext:
    """Enhanced shared context with inter-agent communication."""
    query: str
    raw_data: str
    investigation_stage: str = "discovery"
    
    # Agents and their findings
    agent_contributions: Dict = field(default_factory=dict)
    confidence_scores: Dict = field(default_factory=dict)
    
    # Communication channel
    message_queue: List[AgentMessage] = field(default_factory=list)
    message_history: Dict[str, List[AgentMessage]] = field(default_factory=lambda: defaultdict(list))
    
    # Shared knowledge base
    artifacts: Dict = field(default_factory=dict)
    timeline_events: List = field(default_factory=list)
    threat_actors: List = field(default_factory=list)
    attribution_chain: List = field(default_factory=list)
    vulnerabilities: List = field(default_factory=list)
    indicators: Dict = field(default_factory=dict)  # IOCs by type
    
    # Coordination flags
    active_agents: set = field(default_factory=set)
    waiting_on: Dict = field(default_factory=dict)  # Agent -> depends on whom


class Agent:
    """Enhanced Agent with communication capabilities."""
    
    def __init__(self, name: str, personality: str, role: str, behavior: str, division: str = ""):
        self.name = name
        self.personality = personality
        self.role = role
        self.behavior = behavior
        self.division = division  # Investigation Division, Hackers, Experts, etc.
        self.findings = {}
        self.confidence = 0.0
        self.message_inbox = []
        self.message_outbox = []
        
    def get_system_prompt(self, include_context: bool = True) -> str:
        """Build system prompt with personality + role + behavior."""
        prompt = f"""You are {self.name}.

PERSONALITY:
{self.personality}

ROLE:
{self.role}

BEHAVIOR:
{self.behavior}

"""
        if include_context:
            prompt += """
You are part of a collaborative 24+ agent threat investigation team. You can:
- Query other agents for specific information
- Request analysis from specialists
- Share findings with relevant team members

Always be clear about your findings and confidence levels.
Specify when you need input from other agents.
Format agent queries as: QUERY→[AGENT_NAME]: [specific question]
"""
        return prompt
    
    def send_message(self, recipient: str, message_type: str, content: str, context_id: str = "") -> AgentMessage:
        """Send a message to another agent."""
        msg = AgentMessage(
            sender=self.name,
            recipient=recipient,
            message_type=message_type,
            content=content,
            context_id=context_id,
        )
        self.message_outbox.append(msg)
        return msg
    
    def receive_message(self, msg: AgentMessage):
        """Receive a message from another agent."""
        self.message_inbox.append(msg)
    
    def to_dict(self) -> dict:
        """Export agent state."""
        return {
            "name": self.name,
            "division": self.division,
            "findings": self.findings,
            "confidence": self.confidence,
            "messages_sent": len(self.message_outbox),
            "messages_received": len(self.message_inbox),
        }


def discover_all_agents() -> Dict[str, Agent]:
    """
    Dynamically discover and load ALL agents from Agents/ folder tree.
    Scans all subdirectories and loads .md/.txt files as agent personalities.
    """
    agents = {}
    
    if not AGENTS_ROOT.exists():
        return agents
    
    # Recursively scan all directories
    for agent_file in AGENTS_ROOT.rglob("*"):
        if (
            agent_file.is_file()
            and agent_file.name not in [".", ".."]
            and agent_file.suffix.lower() in SUPPORTED_AGENT_EXTENSIONS
        ):
            try:
                content = agent_file.read_text(errors="ignore")
                
                # Extract agent name from filename
                agent_name = agent_file.stem.strip()
                division = agent_file.parent.name.strip()
                
                # Parse personality, role, behavior
                personality = extract_section(content, "PERSONALITY:")
                role = extract_section(content, "ROLE:")
                behavior = extract_section(content, "BEHAVIOR:")
                
                if personality and role and behavior:
                    agent = Agent(agent_name, personality, role, behavior, division)
                    agents[agent_name] = agent
            except Exception as e:
                # Silently skip unparseable files
                pass
    
    return agents


def extract_section(text: str, header: str) -> str:
    """Extract a section from agent profile file.

    Supports plain-text headers (PERSONALITY:) and Markdown forms:
    - ## PERSONALITY
    - **PERSONALITY:**
    """
    key = header.rstrip(":")
    section_header = rf"^\s*(?:#+\s*)?(?:\*\*|__)?{re.escape(key)}:?(?:\*\*|__)?\s*$"
    next_header = r"^\s*(?:#+\s*)?(?:\*\*|__)?[A-Z][A-Z0-9\s\-&]{2,}:?(?:\*\*|__)?\s*$"
    pattern = rf"(?ims){section_header}\n(.*?)(?=\n{next_header}|\Z)"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip("\n ")
    return ""


def get_agent_by_name(agents: Dict, name: str) -> Optional[Agent]:
    """Get agent by full or short name."""
    # Try exact match
    if name in agents:
        return agents[name]
    
    # Try short name (e.g., "REAPER" -> "REAPER — Threat Hunter")
    for full_name, agent in agents.items():
        if full_name.startswith(name) or name.upper() in full_name.upper():
            return agent
    
    return None


def get_agents_by_division(agents: Dict, division: str) -> Dict[str, Agent]:
    """Get all agents from a specific division."""
    return {name: agent for name, agent in agents.items() if agent.division == division}


def get_agents_by_capability(agents: Dict, capability_keyword: str) -> Dict[str, Agent]:
    """Get agents whose roles match a capability keyword."""
    keyword = capability_keyword.lower()
    result = {}
    for name, agent in agents.items():
        if (keyword in agent.role.lower() or 
            keyword in agent.personality.lower() or
            keyword in agent.behavior.lower()):
            result[name] = agent
    return result


def list_all_agents(agents: Dict, by_division: bool = True) -> Dict:
    """Organize all agents by division."""
    if by_division:
        divisions = defaultdict(list)
        for name, agent in agents.items():
            divisions[agent.division].append(name)
        return dict(divisions)
    else:
        return list(agents.keys())


def route_message_to_agent(agents: Dict, message: AgentMessage) -> bool:
    """Route a message to the recipient agent."""
    recipient = get_agent_by_name(agents, message.recipient)
    if recipient:
        recipient.receive_message(message)
        return True
    return False


def broadcast_message(agents: Dict, sender_name: str, message_type: str, content: str, context_id: str = "", exclude_sender: bool = True) -> int:
    """Broadcast a message to multiple agents. Returns count of recipients."""
    count = 0
    for agent_name, agent in agents.items():
        if exclude_sender and agent_name == sender_name:
            continue
        msg = AgentMessage(sender_name, agent_name, message_type, content, context_id=context_id)
        agent.receive_message(msg)
        count += 1
    return count
