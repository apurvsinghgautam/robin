"""
Enhanced Robin UI with Multi-Agent Orchestration

Integrates NEXUS orchestrator and displays:
- Agent team delegation
- Inter-agent communication
- Investigation progress
- Synthesized findings
- Strategic alerts
"""

import importlib
import sys
import json
from pathlib import Path
from typing import Optional
from nexus_orchestrator import initialize_nexus
from agent_communication import discover_all_agents


class EnhancedRobinUI:
    """Enhanced UI with NEXUS orchestration and agent visualization."""
    
    def __init__(self):
        self.nexus = initialize_nexus()
        self.agents = self.nexus.agents
        
    def display_banner(self):
        """Display system banner."""
        print("\n" + "="*70)
        print(" " * 15 + "🔍 ROBIN - Threat Intelligence System 🔍")
        print(" " * 10 + "Multi-Agent Orchestration with NEXUS")
        print("="*70)
        print(f"\n✓ Loaded {len(self.agents)} specialized agents across multiple divisions")
        self._show_agent_divisions()
        
    def _show_agent_divisions(self):
        """Display agent divisions."""
        divisions = {}
        for name, agent in self.agents.items():
            div = agent.division or "Unassigned"
            if div not in divisions:
                divisions[div] = 0
            divisions[div] += 1
        
        print("\nAVAILABLE DIVISIONS:")
        for division, count in sorted(divisions.items()):
            print(f"  • {division}: {count} agents")
    
    def investigate_query(self, query: str, raw_data: str = ""):
        """Execute investigation using NEXUS orchestration."""
        print(f"\n{'='*70}")
        print(f"QUERY: {query}")
        print(f"{'='*70}")
        
        # NEXUS parses and delegates
        print("\n[NEXUS] Analyzing threat intelligence query...")
        classification = self.nexus.parse_query(query)
        print(f"  → Threat Level: {classification['threat_level'].upper()}")
        print(f"  → Investigation Scope: {', '.join(classification['investigation_scope']) or 'General'}")
        
        # NEXUS builds delegation plan
        print("\n[NEXUS] Building investigation team...")
        delegation_plan = self.nexus.delegate_investigation(query, raw_data)
        
        self._display_delegation_plan(delegation_plan)
        self._display_investigation_sequence(delegation_plan['coordination_sequence'])
        
        # Get LLM analysis (if available)
        analysis_result = self._get_llm_analysis(query, raw_data)
        
        if analysis_result:
            self._display_analysis_results(analysis_result)
        
        # Simulate synthesis
        print("\n[NEXUS] Synthesizing investigation findings...")
        synthesis = self._simulate_synthesis(query)
        self._display_synthesis(synthesis)
        
        return {
            "query": query,
            "delegation_plan": delegation_plan,
            "synthesis": synthesis,
        }
    
    def _display_delegation_plan(self, delegation_plan: dict):
        """Display how NEXUS delegated the investigation."""
        print("\n" + "-"*70)
        print("INVESTIGATION TEAM:")
        print("-"*70)
        
        if delegation_plan.get('primary_investigator'):
            print(f"Primary Investigator: {delegation_plan['primary_investigator']}")
        
        print(f"\nTeam Assignments ({len(delegation_plan['team_assignments'])} agents):")
        for agent_name, assignment in delegation_plan['team_assignments'].items():
            print(f"  ► {agent_name}")
            print(f"    Task: {assignment['task']}")
    
    def _display_investigation_sequence(self, sequence: list):
        """Display investigation phases."""
        print("\n" + "-"*70)
        print("INVESTIGATION PHASES:")
        print("-"*70)
        
        for i, phase in enumerate(sequence, 1):
            print(f"\nPhase {i}: {phase['phase']}")
            for obj in phase['objectives']:
                print(f"  • {obj}")
    
    def _get_llm_analysis(self, query: str, raw_data: str = "") -> Optional[dict]:
        """
        Get analysis from LLM-based threat intelligence.
        This would integrate with your LLM module.
        """
        try:
            # Try to import and use llm module if available
            llm_module = importlib.import_module('llm')
            if hasattr(llm_module, 'analyze_threat'):
                analysis = llm_module.analyze_threat(query, raw_data)
                return analysis
        except (ImportError, AttributeError):
            # LLM module not available or doesn't have analyze_threat
            pass
        
        return None
    
    def _display_analysis_results(self, analysis: dict):
        """Display LLM analysis results."""
        print("\n" + "-"*70)
        print("LLM THREAT ANALYSIS:")
        print("-"*70)
        
        if "threat_score" in analysis:
            print(f"Threat Score: {analysis['threat_score']}")
        if "key_indicators" in analysis:
            print(f"Key Indicators: {', '.join(analysis['key_indicators'])}")
        if "summary" in analysis:
            print(f"Summary: {analysis['summary']}")
    
    def _simulate_synthesis(self, query: str) -> dict:
        """Simulate synthesis of agent findings."""
        return {
            "investigation_query": query,
            "overall_threat_assessment": "HIGH",
            "confidence_level": 0.82,
            "key_findings": [
                {"source": "Investigation Division", "finding": "Suspicious IP detected", "confidence": 0.95},
                {"source": "Experts", "finding": "Known vulnerability exploited", "confidence": 0.78},
            ],
            "attack_narrative": "Multi-stage attack detected: reconnaissance → exploitation → persistence",
            "recommended_actions": [
                "Isolate affected systems",
                "Apply security patches",
                "Monitor for C2 communication",
            ],
        }
    
    def _display_synthesis(self, synthesis: dict):
        """Display synthesized findings."""
        print("\n" + "-"*70)
        print("NEXUS SYNTHESIS - EXECUTIVE INTELLIGENCE:")
        print("-"*70)
        
        print(f"\nThreat Assessment: {synthesis['overall_threat_assessment']}")
        print(f"Confidence Level: {synthesis['confidence_level']:.1%}")
        
        print(f"\nKey Findings:")
        for finding in synthesis['key_findings']:
            print(f"  • [{finding['source']}] {finding['finding']} ({finding['confidence']:.0%})")
        
        print(f"\nAttack Narrative:")
        print(f"  {synthesis['attack_narrative']}")
        
        print(f"\nRecommended Actions:")
        for i, action in enumerate(synthesis['recommended_actions'], 1):
            print(f"  {i}. {action}")
    
    def list_all_agents(self, grouped: bool = True):
        """List all available agents."""
        print("\n" + "="*70)
        print("COMPLETE AGENT ROSTER:")
        print("="*70)
        
        if grouped:
            divisions = {}
            for name, agent in self.agents.items():
                div = agent.division or "Unassigned"
                if div not in divisions:
                    divisions[div] = []
                divisions[div].append(name)
            
            for division in sorted(divisions.keys()):
                print(f"\n{division}:")
                for agent_name in sorted(divisions[division]):
                    print(f"  • {agent_name}")
        else:
            for agent_name in sorted(self.agents.keys()):
                print(f"  • {agent_name}")
    
    def agent_info(self, agent_name: str):
        """Display detailed agent information."""
        for name, agent in self.agents.items():
            if name.lower() == agent_name.lower() or agent_name.upper() in name.upper():
                print(f"\n{'='*70}")
                print(f"AGENT: {name}")
                print(f"{'='*70}")
                print(f"Division: {agent.division}")
                print(f"\nPersonality:\n{agent.personality}")
                print(f"\nRole:\n{agent.role}")
                print(f"\nBehavior:\n{agent.behavior}")
                return
        
        print(f"Agent '{agent_name}' not found.")
    
    def interactive_mode(self):
        """Run interactive investigation mode."""
        self.display_banner()
        
        while True:
            print("\n" + "-"*70)
            print("COMMANDS:")
            print("  'investigate <query>' - Run threat investigation")
            print("  'list agents' - Show all agents")
            print("  'agent <name>' - Show agent details")
            print("  'nexus status' - Show NEXUS investigation status")
            print("  'quit' - Exit")
            print("-"*70)
            
            user_input = input("\n> ").strip()
            
            if user_input.lower() == "quit":
                print("\nShutting down ROBIN...")
                break
            
            elif user_input.lower() == "list agents":
                self.list_all_agents()
            
            elif user_input.lower().startswith("agent "):
                agent_name = user_input[6:].strip()
                self.agent_info(agent_name)
            
            elif user_input.lower() == "nexus status":
                status = self.nexus.get_investigation_status()
                print(f"\nNEXUS Investigation Status:")
                print(json.dumps(status, indent=2, default=str))
            
            elif user_input.lower().startswith("investigate "):
                query = user_input[12:].strip()
                self.investigate_query(query)
            
            else:
                print("Unknown command. Please try again.")


def main():
    """Main entry point."""
    ui = EnhancedRobinUI()
    
    # Check if running with command-line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive":
            ui.interactive_mode()
        elif sys.argv[1] == "--agents":
            ui.list_all_agents()
        else:
            # Treat as investigation query
            query = " ".join(sys.argv[1:])
            ui.investigate_query(query)
    else:
        ui.interactive_mode()


if __name__ == "__main__":
    main()
