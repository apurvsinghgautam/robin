"""
Multi-Agent Orchestrator

Orchestrates the investigation workflow with specialized agents working in sequence.
Manages context sharing, evidence tracking, and final report generation.
"""

from typing import Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from agents import AgentContext, get_agent, AGENT_ROSTER
from llm_utils import sanitize_input
import json
from datetime import datetime


class InvestigationOrchestrator:
    """Orchestrates multi-agent dark web investigation workflow."""
    
    def __init__(self, llm):
        self.llm = llm
        self.context = None
        self.agent_results = {}
        self.workflow_log = []
        
    def initialize_context(self, query: str, raw_data: str) -> AgentContext:
        """Initialize shared context for all agents."""
        self.context = AgentContext(
            query=sanitize_input(query, max_length=1000),
            raw_data=sanitize_input(raw_data, max_length=50000),
            investigation_stage="discovery",
        )
        return self.context
    
    def log_stage(self, agent_name: str, status: str, details: str = ""):
        """Log workflow progression."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "status": status,
            "details": details,
        }
        self.workflow_log.append(entry)
    
    def run_agent_task(self, agent_short_name: str, task_query: str) -> Dict:
        """
        Run a single agent task within the workflow.
        Returns structured findings from that agent.
        """
        agent = get_agent(agent_short_name)
        if not agent:
            return {"error": f"Agent {agent_short_name} not found"}
        
        system_prompt = agent.get_system_prompt()
        
        # Build agent-specific context
        agent_context = f"""
INVESTIGATION QUERY: {self.context.query}

CURRENT ARTIFACTS: {json.dumps(self.context.artifacts_found, indent=2)}
TIMELINE SO FAR: {json.dumps(self.context.timeline_events, indent=2)}
THREAT ACTORS IDENTIFIED: {json.dumps(self.context.threat_actors, indent=2)}

DATA TO ANALYZE:
{self.context.raw_data[:10000]}  [truncated for agent focus]

YOUR TASK:
{task_query}

Respond with structured findings. Be specific. State confidence levels.
"""
        
        prompt_template = ChatPromptTemplate(
            [("system", system_prompt), ("user", "{context}")]
        )
        chain = prompt_template | self.llm | StrOutputParser()
        
        try:
            result = chain.invoke({"context": agent_context})
            self.log_stage(agent_short_name, "completed", f"Task complete")
            return {
                "agent": agent_short_name,
                "status": "success",
                "findings": result,
            }
        except Exception as e:
            self.log_stage(agent_short_name, "failed", str(e))
            return {
                "agent": agent_short_name,
                "status": "error",
                "error": str(e),
            }
    
    def run_dark_web_investigation_workflow(self) -> Dict:
        """
        Master workflow for dark web investigations.
        Runs: REAPER → TRACE → LEDGER → FLUX → MASON → VEIL → BISHOP → GHOST
        """
        results = {
            "query": self.context.query,
            "workflow": [],
            "final_report": "",
            "timeline": self.workflow_log,
        }
        
        # Stage 1: REAPER - Initial threat hunting and hypothesis
        reaper_result = self.run_agent_task(
            "REAPER",
            "Identify threat hypotheses, hunting patterns, and suspicious behavior in this data. What should we look for?"
        )
        results["workflow"].append(reaper_result)
        self.context.investigation_stage = "threat_hunting"
        
        # Stage 2: TRACE - Digital forensics
        trace_result = self.run_agent_task(
            "TRACE",
            "Extract forensic artifacts: file references, metadata, timestamps, deleted items. What evidence remains?"
        )
        results["workflow"].append(trace_result)
        self.context.investigation_stage = "forensics"
        
        # Stage 3: LEDGER - Blockchain/payment tracing (if applicable)
        ledger_result = self.run_agent_task(
            "LEDGER",
            "Extract and trace cryptocurrency addresses, wallet clusters, payment flows. Follow the money."
        )
        results["workflow"].append(ledger_result)
        self.context.investigation_stage = "payment_tracing"
        
        # Stage 4: FLUX - Timeline reconstruction
        flux_result = self.run_agent_task(
            "FLUX",
            "Build a complete timeline from all available timestamps and events. Identify key decision points and sequences."
        )
        results["workflow"].append(flux_result)
        self.context.investigation_stage = "timeline_analysis"
        
        # Stage 5: MASON - Incident response context
        mason_result = self.run_agent_task(
            "MASON",
            "Frame this within an IR lifecycle. What was the attack? Contain? Eradicate? Recover? Lessons learned?"
        )
        results["workflow"].append(mason_result)
        self.context.investigation_stage = "incident_response"
        
        # Stage 6: VEIL - Dark web context and ecosystem research
        veil_result = self.run_agent_task(
            "VEIL",
            "Provide dark web ecosystem context. What does this tell us about market structures, threat actor operations, or forum dynamics?"
        )
        results["workflow"].append(veil_result)
        self.context.investigation_stage = "dark_web_context"
        
        # Stage 7: BISHOP - Attribution
        bishop_result = self.run_agent_task(
            "BISHOP",
            "Assess threat actor attribution. Who did this? State confidence levels. What is the motive, means, opportunity?"
        )
        results["workflow"].append(bishop_result)
        self.context.investigation_stage = "attribution"
        
        # Stage 8: GHOST - Behavioral profiling and social analysis
        ghost_result = self.run_agent_task(
            "GHOST",
            "Profile threat actor behavior, communication patterns, group structure, and operational security posture."
        )
        results["workflow"].append(ghost_result)
        self.context.investigation_stage = "profiling"
        
        # Compile final integrated report
        results["final_report"] = self._synthesize_findings(results["workflow"])
        
        return results
    
    def _synthesize_findings(self, workflow_results: List[Dict]) -> str:
        """
        Synthesize all agent findings into a comprehensive, integrated report.
        """
        report_sections = []
        
        report_sections.append("# MULTI-AGENT INVESTIGATION REPORT\n")
        report_sections.append(f"**Investigation Query:** {self.context.query}\n")
        report_sections.append(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        
        report_sections.append("## INVESTIGATION OVERVIEW\n")
        report_sections.append("This investigation deployed 8 specialized agents in sequence:\n")
        report_sections.append("1. **REAPER** (Threat Hunter) — Identified threat hypotheses and hunting patterns\n")
        report_sections.append("2. **TRACE** (Forensics) — Extracted forensic artifacts and evidence\n")
        report_sections.append("3. **LEDGER** (Blockchain) — Traced cryptocurrency transactions and wallets\n")
        report_sections.append("4. **FLUX** (Timeline) — Reconstructed complete incident timeline\n")
        report_sections.append("5. **MASON** (IR) — Framed within incident response lifecycle\n")
        report_sections.append("6. **VEIL** (Dark Web) — Provided ecosystem and market context\n")
        report_sections.append("7. **BISHOP** (Attribution) — Assessed threat actor attribution\n")
        report_sections.append("8. **GHOST** (Profiling) — Built behavioral and social profiles\n\n")
        
        report_sections.append("## FINDINGS BY AGENT\n")
        for result in workflow_results:
            if result.get("status") == "success":
                agent_name = result.get("agent", "Unknown")
                findings = result.get("findings", "No findings")
                report_sections.append(f"\n### {agent_name}\n")
                report_sections.append(f"{findings}\n")
        
        report_sections.append("\n## INTEGRATED ANALYSIS\n")
        report_sections.append("This multi-agent report synthesizes findings across forensic, financial, temporal, ")
        report_sections.append("and attribution dimensions to provide comprehensive threat intelligence.\n\n")
        
        report_sections.append("---\n")
        report_sections.append(f"Report generated at {datetime.now().isoformat()}\n")
        
        return "".join(report_sections)
    
    def get_workflow_status(self) -> Dict:
        """Get current workflow progress."""
        return {
            "stage": self.context.investigation_stage,
            "agents_completed": len([r for r in self.agent_results.values() if r.get("status") == "success"]),
            "agents_failed": len([r for r in self.agent_results.values() if r.get("status") == "error"]),
            "log": self.workflow_log,
        }
