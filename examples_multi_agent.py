#!/usr/bin/env python3
"""
Example: Using Robin's Multi-Agent System

Demonstrates how to use NEXUS orchestrator and the 24+ agent team
for threat investigations.
"""

from nexus_orchestrator import initialize_nexus
from agent_communication import (
    discover_all_agents,
    get_agents_by_division,
    get_agents_by_capability,
    Agent
)


def example_1_basic_query_investigation():
    """Example 1: Simple threat investigation"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Threat Investigation")
    print("="*70)
    
    # Initialize NEXUS
    nexus = initialize_nexus()
    
    # Setup query
    query = "Investigate suspicious domain malware.example.com"
    
    # NEXUS analyzes and delegates
    classification = nexus.parse_query(query)
    print(f"\nQuery Classification:")
    print(f"  Threat Level: {classification['threat_level']}")
    print(f"  Investigation Scope: {classification['investigation_scope']}")
    
    # Build investigation team
    delegation = nexus.delegate_investigation(query)
    print(f"\nTeam Size: {len(delegation['team_assignments'])} agents")
    print(f"Primary Investigator: {delegation['primary_investigator']}")
    
    # Show phases
    print(f"\nInvestigation Phases:")
    for phase in delegation['coordination_sequence']:
        print(f"  → {phase['phase']}")


def example_2_agent_discovery():
    """Example 2: Discovering all available agents"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Discovering All Agents")
    print("="*70)
    
    agents = discover_all_agents()
    print(f"\nTotal Agents Discovered: {len(agents)}")
    
    # Group by division
    divisions = {}
    for name, agent in agents.items():
        div = agent.division or "Unassigned"
        if div not in divisions:
            divisions[div] = []
        divisions[div].append(name)
    
    print("\nAgents by Division:")
    for division in sorted(divisions.keys()):
        print(f"\n{division} ({len(divisions[division])} agents):")
        for agent_name in sorted(divisions[division])[:5]:  # Show first 5
            print(f"  • {agent_name}")
        if len(divisions[division]) > 5:
            print(f"  ... and {len(divisions[division]) - 5} more")


def example_3_capability_based_querying():
    """Example 3: Finding agents by capability"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Finding Agents by Capability")
    print("="*70)
    
    agents = discover_all_agents()
    
    # Find malware analysis specialists
    capabilities = ["malware", "reverse", "exploit", "vulnerability", "attribution"]
    
    for capability in capabilities:
        specialists = get_agents_by_capability(agents, capability)
        if specialists:
            print(f"\n{capability.upper()} specialists ({len(specialists)} agents):")
            for agent_name in list(specialists.keys())[:3]:
                print(f"  • {agent_name}")


def example_4_investigation_coordination():
    """Example 4: Multi-stage investigation with agent coordination"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Multi-Stage Investigation Coordination")
    print("="*70)
    
    nexus = initialize_nexus()
    
    # Scenario: Investigate APT campaign
    query = "Analyze APT campaign targeting financial institutions"
    raw_data = """
    IOCs: 192.168.1.100, example.com, malware.exe
    Timeline: Campaign started March 2024
    Targets: US, UK, Japan financial institutions
    Methods: Spear phishing, zero-days
    """
    
    # Get delegation plan
    plan = nexus.delegate_investigation(query, raw_data)
    
    print(f"\nInvestigation: {query}")
    print(f"Threat Level: {plan['threat_level']}")
    
    # Show investigation sequence
    print(f"\nCoordinated Investigation Phases:")
    for i, phase in enumerate(plan['coordination_sequence'], 1):
        print(f"\n  Phase {i}: {phase['phase']}")
        print(f"  Assigned Agents: {', '.join(phase['agents'][:2])}")
        for objective in phase['objectives'][:2]:
            print(f"    • {objective}")
    
    # Show expected outputs
    print(f"\nExpected Investigation Outputs:")
    for output_type, description in plan['expected_outputs'].items():
        print(f"  • {output_type}: {description}")


def example_5_agent_communication():
    """Example 5: Simulating inter-agent communication"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Inter-Agent Communication")
    print("="*70)
    
    agents = discover_all_agents()
    
    if not agents:
        print("No agents discovered. Please ensure agent files are in Agents/ folder.")
        return
    
    # Get two agents to demonstrate communication
    agent_list = list(agents.items())
    if len(agent_list) < 2:
        print(f"Only {len(agent_list)} agent(s) available. Need at least 2 for demonstration.")
        return
    
    agent1_name, agent1 = agent_list[0]
    agent2_name, agent2 = agent_list[1]
    
    print(f"\nDemonstrating communication between:")
    print(f"  Agent 1: {agent1_name}")
    print(f"  Agent 2: {agent2_name}")
    
    # Simulate query
    query_msg = agent1.send_message(
        recipient=agent2_name,
        message_type="query",
        content="Have you encountered this threat actor before?",
        context_id="investigation_001"
    )
    
    print(f"\n[Query from {agent1_name} to {agent2_name}]")
    print(f"  Message Type: {query_msg.message_type}")
    print(f"  Content: {query_msg.content}")
    
    # Simulate response
    agent2.receive_message(query_msg)
    response_msg = agent2.send_message(
        recipient=agent1_name,
        message_type="response",
        content="Yes, they were active in March 2024 targeting energy sector.",
        context_id="investigation_001"
    )
    
    print(f"\n[Response from {agent2_name} to {agent1_name}]")
    print(f"  Message Type: {response_msg.message_type}")
    print(f"  Content: {response_msg.content}")
    
    # Check message queues
    print(f"\nCommunication Status:")
    print(f"  {agent1_name} received: {len(agent1.message_inbox)} messages")
    print(f"  {agent2_name} received: {len(agent2.message_inbox)} messages")


def example_6_nexus_synthesis():
    """Example 6: NEXUS synthesizing findings"""
    print("\n" + "="*70)
    print("EXAMPLE 6: NEXUS Synthesizing Findings")
    print("="*70)
    
    nexus = initialize_nexus()
    
    # Simulate investigation with findings
    nexus.context.query = "Check IP 192.168.1.1 for malicious activity"
    nexus.context.agent_contributions = {
        "Investigation Division": "IP linked to previous campaigns",
        "Threat Intelligence": "Associated with APT28",
        "Experts": "Matches exploit delivery pattern",
    }
    nexus.context.confidence_scores = {
        "Investigation Division": 0.95,
        "Threat Intelligence": 0.88,
        "Experts": 0.82,
    }
    nexus.context.timeline_events = [
        "IP first seen March 2024",
        "Reconnaissance activity detected",
        "Exploit delivery attempted",
        "Persistence established",
    ]
    nexus.context.threat_actors = ["APT28"]
    
    # Synthesize findings
    synthesis = nexus.synthesize_findings()
    
    print(f"\nInvestigation Query: {synthesis['investigation_query']}")
    print(f"Threat Assessment: {synthesis['overall_threat_assessment']}")
    print(f"Confidence: {synthesis['confidence_level']:.1%}")
    
    print(f"\nKey Findings:")
    for finding in synthesis['key_findings'][:3]:
        print(f"  • [{finding['source']}] {finding['finding']}")
    
    if synthesis.get('attack_narrative'):
        print(f"\nAttack Narrative:")
        for line in synthesis['attack_narrative'].split('\n')[:3]:
            if line.strip():
                print(f"  {line}")
    
    print(f"\nCritical Alerts:")
    for alert in synthesis.get('critical_alerts', []):
        print(f"  ⚠ {alert}")


def example_7_agent_profiles():
    """Example 7: Displaying detailed agent profiles"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Detailed Agent Profile")
    print("="*70)
    
    agents = discover_all_agents()
    
    if not agents:
        print("No agents discovered.")
        return
    
    # Show first agent's full profile
    agent_name, agent = list(agents.items())[0]
    
    print(f"\nAgent: {agent_name}")
    print(f"Division: {agent.division}")
    
    print(f"\nPersonality:")
    print(f"  {agent.personality[:300]}...")
    
    print(f"\nRole:")
    print(f"  {agent.role[:300]}...")
    
    print(f"\nBehavior:")
    print(f"  {agent.behavior[:300]}...")


def main():
    """Run all examples"""
    print("\n" + "🔍"*35)
    print("ROBIN Multi-Agent System Examples")
    print("🔍"*35)
    
    examples = [
        ("Basic Query Investigation", example_1_basic_query_investigation),
        ("Agent Discovery", example_2_agent_discovery),
        ("Capability-Based Querying", example_3_capability_based_querying),
        ("Investigation Coordination", example_4_investigation_coordination),
        ("Inter-Agent Communication", example_5_agent_communication),
        ("NEXUS Synthesis", example_6_nexus_synthesis),
        ("Agent Profiles", example_7_agent_profiles),
    ]
    
    print("\nRunning Examples...")
    print("-"*70)
    
    for i, (name, example_func) in enumerate(examples, 1):
        try:
            example_func()
        except Exception as e:
            print(f"\n⚠ Example {i} ({name}) encountered error: {e}")
    
    print("\n" + "="*70)
    print("Examples Complete!")
    print("="*70)
    print("\nTo explore the system further:")
    print("  python enhanced_ui.py --interactive")
    print("  python enhanced_ui.py --agents")
    print("  python enhanced_ui.py 'investigate <query>'")


if __name__ == "__main__":
    main()
