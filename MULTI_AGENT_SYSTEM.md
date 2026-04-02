># Robin Enhanced Multi-Agent System Documentation

## System Architecture

The enhanced Robin system implements a **strategic 24+ agent orchestration framework** with NEXUS as the master commander.

### Core Components

#### 1. **agent_communication.py** - Inter-Agent Communication Framework

**Key Classes:**
- `Agent` - Individual agent with personality, role, and behavior
- `AgentContext` - Shared context with inter-agent messaging
- `AgentMessage` - Messages passed between agents

**Key Functions:**
- `discover_all_agents()` - Dynamically loads ALL agents from `Agents/` folder tree
- `get_agents_by_division()` - Filter agents by division
- `get_agents_by_capability()` - Find agents with specific capabilities
- `route_message_to_agent()` - Direct routing between agents
- `broadcast_message()` - Send message to multiple agents

**Features:**
- Dynamic agent discovery (scans all subdirectories)
- Inter-agent message passing with context tracking
- Specialized message types: query, response, finding, alert, coordination
- Shared knowledge base for investigation artifacts

#### 2. **nexus_orchestrator.py** - Strategic Master Commander

**NEXUS Capabilities:**
- **Query Analysis** - Classifies incoming threats by urgency and scope
- **Team Delegation** - Assigns specialized agents to investigation phases
- **Phase Orchestration** - Discovery → Actor Analysis → Malware Analysis → Vulnerability Assessment → Synthesis
- **Evidence Synthesis** - Weaves agent findings into coherent attack narratives
- **Strategic Decision Making** - Applies risk/impact matrices for final assessments
- **Alert Escalation** - Raises critical alerts with confidence metrics

**Key Methods:**
```python
nexus = initialize_nexus()

# Delegate investigation to specialized teams
delegation_plan = nexus.delegate_investigation(query, raw_data)
# Returns: team assignments, coordination sequence, expected outputs

# Synthesize multi-agent findings
synthesis = nexus.synthesize_findings()
# Returns: threat assessment, confidence level, key findings, attack narrative

# Raise strategic alerts
alert = nexus.raise_alert("CRITICAL", "APT campaign confirmed", evidence)

# Get investigation status
status = nexus.get_investigation_status()
```

#### 3. **enhanced_ui.py** - User-Facing Interface

**Interactive Commands:**
- `investigate <query>` - Run full investigation
- `list agents` - Show all 24+ agents by division
- `agent <name>` - Display agent details
- `nexus status` - Show current investigation status
- `quit` - Exit

**Features:**
- Displays agent team delegation
- Shows investigation phases and objectives
- Integrates with LLM analysis (if available)
- Shows synthesized findings and recommendations
- Interactive investigation mode

---

## How It Works: Complete Workflow

### 1. **Query Reception**
```
User Input: "Investigate suspicious IP 192.168.1.1"
    ↓
Enhanced_UI receives query
```

### 2. **NEXUS Analysis & Classification**
```
NEXUS parses query:
  • Threat Level: HIGH
  • Investigation Scope: indicators, attribution
  • Required Divisions: Investigation Division, Experts
```

### 3. **Team Delegation**
```
NEXUS builds investigation team:
  ✓ Investigation Division agents
    - REAPER (Threat Hunter)
    - IRIS (Threat Intel)
    - CIPHER (Data Analyst)
  ✓ Expert agents
    - PHOENIX (Security Researchers)
    - ATLAS (Knowledge Base)
```

### 4. **Investigation Phases** (Coordinated by NEXUS)
```
Phase 1: Discovery
  └─ Investigation Division investigates indicators
  
Phase 2: Actor Analysis  
  └─ Threat Intelligence links to known actors
  
Phase 3: Synthesis
  └─ NEXUS weaves findings into attack narrative
```

### 5. **Inter-Agent Communication**
During investigation, agents can:
- Query each other for specific information
- Share findings with relevant team members
- Coordinate on complex investigations
- Build evidence chains together

Example:
```
IRIS (Threat Intel) → REAPER (Threat Hunter):
  "Have you seen these IOCs before? Any known campaigns?"

REAPER → IRIS:
  "Yes, pattern matches APT28. Last seen June 2023 targeting energy sector."
```

### 6. **Finding Synthesis**
```
NEXUS combines:
  • REAPER's indicators (confidence: 0.95)
  • IRIS's actor link (confidence: 0.88)
  • PHOENIX's vulnerability assessment (confidence: 0.82)
    ↓
Overall Assessment: HIGH (average confidence: 0.88)
```

### 7. **Executive Intelligence Output**
```
THREAT ASSESSMENT: HIGH
CONFIDENCE: 88%

KEY FINDINGS:
  • [Investigation] IP linked to APT28 infrastructure
  • [Experts] CVE-2024-XXX actively exploited
  • [Threat Intel] Recent campaign targeting energy sector

ATTACK NARRATIVE:
  Multi-stage attack: reconnaissance → exploitation → persistence

RECOMMENDATIONS:
  1. Isolate affected systems
  2. Apply critical patches
  3. Monitor for C2 communication
```

---

## Agent Discovery & Loading

### Automatic Discovery
Robin automatically discovers agents from the `Agents/` folder structure:

```
Agents/
├── Investigation Division/
│   ├── REAPER.txt (Threat Hunter)
│   ├── IRIS.txt (Threat Intelligence)
│   ├── CIPHER.txt (Data Analyst)
│   └── ...
├── Hackers/
│   ├── NOVA.txt (Malware Reverser)
│   ├── BYTE.txt (Exploit Developer)
│   └── ...
├── Experts/
│   ├── PHOENIX.txt (Security Researcher)
│   ├── ATLAS.txt (Knowledge Base)
│   └── ...
└── ...
```

### Dynamic Discovery Algorithm
```python
discover_all_agents():
  1. Recursively scan Agents/ folder (all subdirectories)
  2. For each file found:
     - Extract agent name from filename
     - Extract division from folder name
     - Parse personality, role, behavior sections
     - Create Agent object
  3. Return dict of all discovered agents
```

### Adding New Agents
1. Create agent file in appropriate division folder
2. Include PERSONALITY, ROLE, BEHAVIOR sections
3. System auto-discovers on next initialization

---

## Agent Communication Protocol

### Message Types

#### 1. Query
Agent requests information from another
```python
msg = agent1.send_message(
    recipient="IRIS",
    message_type="query",
    content="Have you investigated this IP before?",
    context_id="investigation_12345"
)
```

#### 2. Response
Agent responds to a query
```python
msg = agent2.send_message(
    recipient="REAPER",
    message_type="response",
    content="Yes, linked to APT28 campaign from March 2024",
    context_id="investigation_12345"
)
```

#### 3. Finding
Agent shares investigation finding
```python
msg = agent.send_message(
    recipient="NEXUS",
    message_type="finding",
    content="Confidence level: 0.95, Evidence: X",
    context_id="investigation_12345"
)
```

#### 4. Alert
Agent raises alert to team
```python
msg = agent.send_message(
    recipient="NEXUS",
    message_type="alert",
    content="CRITICAL: C2 communication detected",
    context_id="investigation_12345"
)
```

#### 5. Coordination
Agent requests collaboration
```python
msg = agent.send_message(
    recipient="PHOENIX",
    message_type="coordination",
    content="Need expert analysis on this vulnerability",
    context_id="investigation_12345"
)
```

---

## Integration with Existing Robin Modules

### LLM Integration
The enhanced system can integrate with your existing LLM module:

```python
# In enhanced_ui.py
analysis = llm.analyze_threat(query, raw_data)
# Returns threat score, indicators, summary
```

### Scraping Integration
```python
# In enhanced_ui.py or investigation workflow
url_results = scrape.collect_threat_data(indicators)
# Feeds data into investigation pipeline
```

### Search Integration
```python
# In investigation workflow
search_results = search.query_threat_intelligence(iocs)
# Used by Investigation Division agents
```

---

## Configuration & Customization

### Threat Level Thresholds
Override in `NEXUSOrchestrator`:
```python
nexus.critical_threat_threshold = 0.85
nexus.medium_threat_threshold = 0.60
```

### Investigation Phases
Customize in `_build_coordination_sequence()`:
```python
sequence.append({
    "phase": "Custom Phase",
    "agents": ["Agent1", "Agent2"],
    "objectives": ["Objective 1", "Objective 2"],
})
```

### Agent Capabilities
Query by keyword:
```python
experts = get_agents_by_capability(agents, "malware analysis")
```

---

## Example: Complete Investigation

```python
from enhanced_ui import EnhancedRobinUI

# Initialize system
ui = EnhancedRobinUI()

# Run investigation
result = ui.investigate_query(
    query="Analyze suspicious campaign targeting finance sector",
    raw_data=raw_IOC_data
)

# Results include:
# - Delegation plan (which agents did what)
# - Investigation phases and findings
# - Synthesized threat assessment
# - Strategic recommendations
# - Confidence metrics
```

---

## Performance Characteristics

- **Agent Discovery**: ~100ms for typical 24+ agent setup
- **Query Classification**: ~50ms
- **Team Delegation**: ~75ms
- **Message Routing**: <1ms per message
- **Synthesis**: Depends on agent findings volume

---

## Extension Points

### 1. Add New Agents
```
Agents/[Division]/[AgentName].txt
```

### 2. Add New Message Types
```python
# In AgentMessage dataclass
message_type: str  # Add new type to enum
```

### 3. Add New Investigation Phases
```python
# In nexus_orchestrator.py _build_coordination_sequence()
sequence.append({ ... })
```

### 4. Custom Synthesis Logic
```python
# Override synthesize_findings() in NEXUSOrchestrator
```

---

## Key Advantages

1. **Scalability** - Dynamically discovers any number of agents
2. **Modularity** - Agents can be added without code changes
3. **Collaboration** - Inter-agent communication enables complex investigations
4. **Strategic** - NEXUS makes authoritative decisions based on evidence
5. **Extensibility** - Easy to add new phases, message types, capabilities
6. **Transparency** - Investigation log shows all decision-making steps

---

## Troubleshooting

### Agents Not Being Discovered
- Verify agent files are in `Agents/` subdirectories
- Check file contains PERSONALITY, ROLE, BEHAVIOR sections
- Look at discovery_log for parsing errors

### Message Routing Issues
- Ensure recipient agent name is correct
- Check agent division and capabilities match query
- Review message_inbox on recipient agent

### Investigation Completion Errors
- Verify all delegated agents completed analysis
- Check synthesis has required findings
- See NEXUS investigation_log for details

---

## Future Enhancements

- Real-time agent performance metrics
- Learning between investigations (pattern storage)
- Automatic agent capability discovery from profile files
- Machine learning-based team optimization
- Integration with external threat feeds
- Persistent investigation repository
