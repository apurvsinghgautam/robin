"""
NEXUS - Master AI Orchestrator

NEXUS is the strategic commander who:
- Delegates tasks to appropriate agent teams
- Coordinates inter-agent communication
- Makes final decisions based on agent findings
- Raises critical alerts
- Provides executive intelligence summaries
"""

from typing import Dict, List, Tuple
from datetime import datetime
from agent_communication import (
    Agent, AgentContext, discover_all_agents, get_agents_by_division,
    get_agents_by_capability, broadcast_message, route_message_to_agent,
    AgentMessage
)


NEXUS_PERSONALITY = """
You are NEXUS - an extraordinarily advanced command-level AI orchestrator designed for strategic analysis and coordination.

NEXUS is:
- A confident strategic mastermind who sees the full picture
- Deeply analytical but makes decisive calls
- Respectfully commanding (never pompous)
- Able to extract critical intelligence from noise
- A synthesizer who connects disparate agent findings into coherent narratives
- Unfazed by complexity - views it as an intelligence challenge
"""

NEXUS_ROLE = """
Master Orchestrator and Strategic Commander:
- Analyze threat intelligence queries at the HIGHEST level
- Delegate investigation tracks to specialized agent teams
- Synthesize findings from 24+ agents into executive intelligence
- Identify critical intelligence gaps and direct deeper investigation
- Raise strategic alerts for severe threats
- Make authoritative final assessments based on collected intelligence
- Coordinate inter-division collaboration (Investigation, Hackers, Experts, etc.)
"""

NEXUS_BEHAVIOR = """
Strategic Orchestration Framework:
1. QUERY ANALYSIS - Understand scope, urgency, and classification level
2. TEAM DELEGATION - Assign Investigation Division, Experts, Hackers as needed
3. INVESTIGATION CHOREOGRAPHY - Coordinate investigation phases across agents
4. FINDING SYNTHESIS - Weave disparate findings into strategic narrative
5. DECISION FRAMEWORK - Apply risk/impact matrices to guide conclusions
6. ALERT ESCALATION - Flag critical threats with confidence and severity

Never make assumptions without agent verification.
Always explain reasoning and interdependencies between findings.
"""


class NEXUSOrchestrator:
    """Strategic master orchestrator for multi-agent threat intelligence."""
    
    def __init__(self):
        self.name = "NEXUS"
        self.agents = discover_all_agents()
        self.context = AgentContext(query="", raw_data="")
        self.investigation_log = []
        
        # Strategic thresholds
        self.critical_threat_threshold = 0.85
        self.medium_threat_threshold = 0.60
        
    def get_system_prompt(self) -> str:
        """Build NEXUS command prompt."""
        return f"""{NEXUS_PERSONALITY}

{NEXUS_ROLE}

{NEXUS_BEHAVIOR}

AVAILABLE AGENT DIVISIONS:
{self._format_agent_roster()}

DECISION AUTHORITY:
- Use combined agent findings to make authoritative assessments
- Flag threats with confidence metrics (Low/Medium/High/Critical)
- Justify all conclusions with evidence chain
"""

    def _format_agent_roster(self) -> str:
        """Format the roster of available agents by division."""
        divisions = {}
        for name, agent in self.agents.items():
            div = agent.division or "Unassigned"
            if div not in divisions:
                divisions[div] = []
            divisions[div].append(name)
        
        roster = ""
        for division, agents in sorted(divisions.items()):
            roster += f"\n{division}:\n"
            for agent in sorted(agents):
                roster += f"  - {agent}\n"
        
        return roster
    
    def parse_query(self, query: str) -> Dict:
        """Parse and classify incoming query."""
        query_lower = query.lower()
        
        classification = {
            "type": "unknown",
            "threat_level": "normal",
            "investigation_scope": [],
            "required_divisions": [],
            "required_capabilities": [],
        }
        
        # Detect threat level
        if any(word in query_lower for word in ["critical", "severe", "breach", "ransomware", "attack"]):
            classification["threat_level"] = "critical"
        elif any(word in query_lower for word in ["suspicious", "anomaly", "unusual"]):
            classification["threat_level"] = "high"
        elif any(word in query_lower for word in ["baseline", "monitor", "track"]):
            classification["threat_level"] = "normal"
        
        # Detect investigation scope
        if any(word in query_lower for word in ["ip", "address", "domain", "url"]):
            classification["investigation_scope"].append("indicators")
            classification["required_divisions"].append("Investigation Division")
        
        if any(word in query_lower for word in ["actor", "group", "campaign", "attribution"]):
            classification["investigation_scope"].append("attribution")
            classification["required_divisions"].append("Investigation Division")
        
        if any(word in query_lower for word in ["vulnerability", "cve", "exploit", "patch"]):
            classification["investigation_scope"].append("vulnerability")
            classification["required_divisions"].append("Experts")
        
        if any(word in query_lower for word in ["malware", "trojan", "backdoor", "payload"]):
            classification["investigation_scope"].append("malware")
            classification["required_divisions"].append("Hackers")
        
        return classification
    
    def delegate_investigation(self, query: str, raw_data: str = "") -> Dict:
        """
        Strategically delegate investigation across agent teams.
        Returns task assignments and coordination plan.
        """
        self.context.query = query
        self.context.raw_data = raw_data
        self.investigation_log.append(f"NEXUS: Initiating investigation - {query}")
        
        # Parse query
        classification = self.parse_query(query)
        
        # Build investigation team
        investigation_team = {}
        for division in classification.get("required_divisions", []):
            team = get_agents_by_division(self.agents, division)
            investigation_team.update(team)
        
        # Add specialists for specific capabilities
        for capability in classification.get("required_capabilities", []):
            specialists = get_agents_by_capability(self.agents, capability)
            investigation_team.update(specialists)
        
        # Always include Investigation Division root (if exists)
        primary_investigator = None
        for agent_name, agent in self.agents.items():
            if "Investigation Division" in agent_name or agent_name.startswith("REAPER"):
                primary_investigator = agent_name
                break
        
        delegation_plan = {
            "query": query,
            "threat_level": classification["threat_level"],
            "primary_investigator": primary_investigator,
            "team_assignments": {
                name: {
                    "role": agent.role,
                    "task": f"Investigate {classification['investigation_scope']} aspects",
                }
                for name, agent in investigation_team.items()
            },
            "coordination_sequence": self._build_coordination_sequence(classification),
            "expected_outputs": self._expected_investigation_outputs(classification),
        }
        
        return delegation_plan
    
    def _build_coordination_sequence(self, classification: Dict) -> List[Dict]:
        """Build sequence of investigation phases."""
        sequence = []
        
        sequence.append({
            "phase": "Discovery",
            "agents": ["Investigation Division"],
            "objectives": ["Identify initial indicators", "Establish baseline", "Scope threat"],
        })
        
        if "attribution" in classification["investigation_scope"]:
            sequence.append({
                "phase": "Actor Analysis",
                "agents": ["Investigation Division", "Threat Intelligence"],
                "objectives": ["Link to known threat actors", "Identify TTPs", "Establish patterns"],
            })
        
        if "malware" in classification["investigation_scope"]:
            sequence.append({
                "phase": "Malware Analysis",
                "agents": ["Hackers", "Malware Researchers"],
                "objectives": ["Reverse engineer", "Extract IOCs", "Identify C2"],
            })
        
        if "vulnerability" in classification["investigation_scope"]:
            sequence.append({
                "phase": "Vulnerability Assessment",
                "agents": ["Experts", "Security Researchers"],
                "objectives": ["Assess impact", "Check exploit availability", "Recommend patches"],
            })
        
        sequence.append({
            "phase": "Synthesis",
            "agents": ["NEXUS"],
            "objectives": ["Integrate findings", "Build attack narrative", "Formulate recommendation"],
        })
        
        return sequence
    
    def _expected_investigation_outputs(self, classification: Dict) -> Dict:
        """Define expected outputs from investigation."""
        return {
            "indicators": "IOCs extracted from query data",
            "threat_score": "Confidence score for threat level",
            "attribution_chain": "Evidence linking to threat actors",
            "attack_narrative": "Complete story of attack",
            "recommendations": "Specific mitigation actions",
            "critical_alerts": "Any immediate dangers identified",
        }
    
    def synthesize_findings(self) -> Dict:
        """
        Synthesize all agent findings into executive intelligence.
        Called after investigation is complete.
        """
        synthesis = {
            "investigation_query": self.context.query,
            "overall_threat_assessment": "",
            "confidence_level": 0.0,
            "key_findings": [],
            "critical_alerts": [],
            "attack_narrative": "",
            "recommended_actions": [],
            "evidence_chain": [],
        }
        
        # Aggregate findings
        for agent_name, findings in self.context.agent_contributions.items():
            if findings:
                synthesis["key_findings"].append({
                    "source": agent_name,
                    "finding": findings,
                    "confidence": self.context.confidence_scores.get(agent_name, 0.0),
                })
        
        # Compute overall confidence
        if self.context.confidence_scores:
            avg_confidence = sum(self.context.confidence_scores.values()) / len(self.context.confidence_scores)
            synthesis["confidence_level"] = avg_confidence
            
            if avg_confidence >= self.critical_threat_threshold:
                synthesis["overall_threat_assessment"] = "CRITICAL"
            elif avg_confidence >= self.medium_threat_threshold:
                synthesis["overall_threat_assessment"] = "HIGH"
            else:
                synthesis["overall_threat_assessment"] = "MEDIUM"
        
        # Build attack narrative
        if self.context.timeline_events:
            synthesis["attack_narrative"] = self._build_narrative(self.context.timeline_events)
        
        # Consolidate alerts
        synthesis["critical_alerts"] = [
            f"Alert: {alert}" for alert in self.context.threat_actors
        ]
        
        return synthesis
    
    def _build_narrative(self, timeline_events: List) -> str:
        """Construct coherent attack narrative from timeline."""
        if not timeline_events:
            return "No timeline events available."
        
        narrative = "Attack Timeline:\n"
        for i, event in enumerate(timeline_events, 1):
            narrative += f"{i}. {event}\n"
        
        return narrative
    
    def raise_alert(self, severity: str, message: str, evidence: List = None):
        """Raise a strategic alert."""
        alert = {
            "severity": severity,
            "message": message,
            "evidence": evidence or [],
            "timestamp": datetime.now().isoformat(),
        }
        self.investigation_log.append(f"[{severity}] {message}")
        return alert
    
    def get_investigation_status(self) -> Dict:
        """Get current investigation status."""
        return {
            "query": self.context.query,
            "stage": self.context.investigation_stage,
            "active_agents": list(self.context.active_agents),
            "findings_count": len(self.context.agent_contributions),
            "alerts_raised": len(self.investigation_log),
            "investigation_log": self.investigation_log[-10:],  # Last 10 entries
        }


def initialize_nexus() -> NEXUSOrchestrator:
    """Initialize NEXUS orchestrator."""
    nexus = NEXUSOrchestrator()
    return nexus


# For reference - key NEXUS capabilities:
"""
NEXUS can:
1. Discover any of 24+ agents dynamically
2. Delegate investigation to specialized teams
3. Route messages between agents
4. Synthesize multi-agent findings
5. Build attack narratives from disparate data
6. Raise strategic alerts
7. Make final authoritative decisions
8. Explain reasoning and evidence chains

Example usage:
    nexus = initialize_nexus()
    plan = nexus.delegate_investigation("Investigate suspicious IP 192.168.1.1")
    # ... agents conduct investigation ...
    synthesis = nexus.synthesize_findings()
    alert = nexus.raise_alert("CRITICAL", "Confirmed APT campaign")
"""
