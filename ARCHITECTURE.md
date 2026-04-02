# Robin Multi-Agent System - Architecture & Development Guide

## System Overview
  
```
┌─────────────────────────────────────────────────────────┐
│                   THREAT INTELLIGENCE QUERY             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ENHANCED_UI - Interface & Query Reception              │
│  • Threat input validation                              │
│  • NEXUS orchestration trigger                          │
│  • Results formatting & display                         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  NEXUS_ORCHESTRATOR - Strategic Command                 │
│  • Query classification & threat leveling               │
│  • Team delegation & assignment                         │
│  • Investigation phase orchestration                    │
│  • Finding synthesis & executive decision               │
│  • Alert escalation                                     │
└────────────────────────┬────────────────────────────────┘
                         │
      ┌──────────────────┼──────────────────┐
      │                  │                  │
      ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Investigation│  │   Hackers    │  │   Experts    │
│  Division    │  │  Division    │  │  Division    │
│              │  │              │  │              │
│ • REAPER     │  │ • NOVA       │  │ • PHOENIX    │
│ • IRIS       │  │ • BYTE       │  │ • ATLAS      │
│ • CIPHER     │  │ • MESH       │  │ • SAGE       │
└──────────────┘  └──────────────┘  └──────────────┘
      │                  │                  │
      └──────────────────┼──────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ AGENT_COMMUNICATION - Inter-Agent Collaboration         │
│ • Message routing between agents                        │
│ • Query/Response cycles                                 │
│ • Shared knowledge base                                 │
│ • Context tracking                                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         NEXUS - SYNTHESIS & EXECUTIVE DECISION          │
│ • Combine agent findings                                │
│ • Build attack narratives                               │
│ • Assess confidence levels                              │
│ • Generate recommendations                              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         Executive Intelligence Report (Output)          │
│ • Threat classification                                 │
│ • Key findings with confidence                          │
│ • Attack narrative                                      │
│ • Strategic recommendations                             │
│ • Critical alerts                                       │
└─────────────────────────────────────────────────────────┘
```

## Detailed Component Architecture

### 1. AGENT_COMMUNICATION Layer

**Responsibilities:**
- Dynamic agent discovery from filesystem
- Agent instantiation and state management
- Message passing between agents
- Shared context and artifacts management
- Knowledge base consolidation

**Key Classes:**
```python
class Agent:
    - name: str
    - personality: str
    - role: str
    - behavior: str
    - division: str
    - findings: dict
    - confidence: float
    - message_inbox: list
    - message_outbox: list
    
    Methods:
    - send_message(recipient, msg_type, content, context_id)
    - receive_message(msg)
    - to_dict()
    - get_system_prompt()

class AgentContext:
    - query: str
    - raw_data: str
    - investigation_stage: str
    - agent_contributions: dict          # Agent -> findings
    - confidence_scores: dict             # Agent -> confidence
    - message_queue: list                 # Pending messages
    - message_history: dict               # By sender
    - artifacts: dict                     # Investigation artifacts
    - timeline_events: list               # Attack timeline
    - threat_actors: list                 # Identified actors
    - indicators: dict                    # By type (IP, domain, etc)

class AgentMessage:
    - sender: str
    - recipient: str
    - message_type: str  # query|response|finding|alert|coordination
    - content: str
    - timestamp: str
    - context_id: str
```

**Data Flow:**
```
File System
    ↓
discover_all_agents()
    ↓
Agent objects created
    ↓
AgentContext initialized
    ↓
Messages routed between agents
    ↓
Findings aggregated
```

### 2. NEXUS_ORCHESTRATOR Layer

**Responsibilities:**
- Query classification and threat assessment
- Investigation team delegation algorithm
- Phase sequencing and scheduling
- Finding synthesis and storytelling
- Alert generation and escalation
- Executive decision making

**Key Methods:**

#### Query Classification
```python
parse_query(query: str) -> Dict:
    ├─ Threat level detection
    ├─ Investigation scope identification
    ├─ Required divisions determination
    └─ Capability requirements

Returns:
    {
        "type": "unknown/malware/actor/vulnerability",
        "threat_level": "normal/high/critical",
        "investigation_scope": ["indicators", "attribution"],
        "required_divisions": ["Investigation", "Experts"],
        "required_capabilities": ["malware", "attribution"]
    }
```

#### Team Delegation
```python
delegate_investigation(query, raw_data) -> Dict:
    ├─ Classification analysis
    ├─ Agent discovery
    ├─ Division team selection
    ├─ Capability matching
    ├─ Phase sequencing
    └─ Output specification

Returns:
    {
        "query": query,
        "threat_level": classification["threat_level"],
        "primary_investigator": agent_name,
        "team_assignments": {agent: {role, task}},
        "coordination_sequence": [{phase, agents, objectives}],
        "expected_outputs": {output_type: description}
    }
```

#### Investigation Phases
```
Phase 1: DISCOVERY
    ├─ Investigation Division leads
    ├─ Identify initial indicators
    ├─ Establish baseline
    └─ Scope threat breadth

Phase 2: ACTOR ANALYSIS (if applicable)
    ├─ Threat Intelligence analysis
    ├─ Link to known threat actors
    ├─ Identify TTPs
    └─ Establish behavioral patterns

Phase 3: MALWARE ANALYSIS (if applicable)
    ├─ Hackers Division reverse engineering
    ├─ Extract IOCs
    ├─ Identify C2 infrastructure
    └─ Determine capabilities

Phase 4: VULNERABILITY ASSESSMENT (if applicable)
    ├─ Experts Division evaluation
    ├─ Impact assessment
    ├─ Exploit availability check
    └─ Patch recommendations

Phase 5: SYNTHESIS
    ├─ NEXUS orchestrator leads
    ├─ Integrate findings
    ├─ Build attack narrative
    └─ Formulate recommendations
```

#### Finding Synthesis
```python
synthesize_findings() -> Dict:
    ├─ Aggregate agent contributions
    ├─ Calculate confidence metrics
    ├─ Build attack timeline
    ├─ Construct narrative
    ├─ Identify critical alerts
    └─ Generate recommendations

Returns:
    {
        "threat_assessment": "CRITICAL/HIGH/MEDIUM",
        "confidence_level": 0.85,
        "key_findings": [{source, finding, confidence}],
        "attack_narrative": "story",
        "critical_alerts": ["alert1", "alert2"],
        "recommended_actions": ["action1", "action2"]
    }
```

### 3. ENHANCED_UI Layer

**Responsibilities:**
- User input validation and parsing
- NEXUS orchestrator interface
- Result formatting and display
- Interactive command handling
- Investigation progress visualization

**Command Processing:**
```python
investigate_query(query, raw_data)
    ├─ UI display banner
    ├─ NEXUS parses query
    ├─ Display classification
    ├─ NEXUS delegates investigation
    ├─ Display team assignment
    ├─ Display investigation phases
    ├─ Optional: Get LLM analysis
    ├─ Simulate agent investigation
    ├─ NEXUS synthesis
    └─ Display results

list_all_agents(grouped=True)
    ├─ Discover all agents
    ├─ Group by division (optional)
    └─ Display with counts

agent_info(agent_name)
    ├─ Find agent by name
    ├─ Display personality, role, behavior
    └─ Show division and capabilities

nexus_status()
    ├─ Get investigation state from NEXUS
    ├─ Show active agents
    ├─ Show findings count
    ├─ Display investigation log
    └─ Show alerts raised
```

## Design Patterns

### 1. Dynamic Discovery Pattern
```python
# Agents discovered at runtime from filesystem
agents = discover_all_agents()  # Scans Agents/ folder tree
# No hardcoded agent list - extensible automatically
```

**Benefit:** Add new agents without code changes

### 2. Message Passing Pattern
```python
# Agent-to-agent communication
msg = agent1.send_message(agent2, "query", "content")
agent2.receive_message(msg)
# Decoupled, asynchronous collaboration
```

**Benefit:** Agents work independently while coordinating

### 3. Delegation Pattern
```python
# NEXUS delegates work to specialized teams
team = delegate_investigation(query)
# Classification determines team composition
# Agents execute based on their roles
```

**Benefit:** Optimal team for each investigation type

### 4. Synthesis Pattern
```python
# Combine disparate findings into coherent result
synthesis = synthesize_findings()
# Aggregate → Filter → Analyze → Narrative
```

**Benefit:** Executive-level insight from agent-level details

## Extension Points

### 1. Adding New Agents
```
Create: Agents/[Division]/[Agent_Name].txt

Content:
PERSONALITY:
[personality description]

ROLE:
[role description]

BEHAVIOR:
[behavior description]
```

**Automatic Integration:** System discovers on startup

### 2. Adding New Investigation Phases
```python
# In NEXUS._build_coordination_sequence()
sequence.append({
    "phase": "New Phase",
    "agents": ["Agent1", "Agent2"],
    "objectives": ["Objective 1", "Objective 2"],
})
```

### 3. Adding New Message Types
```python
# In AgentMessage dataclass
message_type: str  # Add new type
# Use in: send_message(..., message_type="new_type", ...)
```

### 4. Custom Synthesis Logic
```python
# Override in NEXUSOrchestrator subclass
def synthesize_findings(self) -> Dict:
    # Custom synthesis algorithm
    pass
```

### 5. Integration Hooks

#### LLM Integration
```python
# In enhanced_ui.py _get_llm_analysis()
analysis = llm.analyze_threat(query, raw_data)
```

#### Scraping Integration
```python
# Use in investigation workflow
data = scrape.collect_threat_data(indicators)
```

#### Search Integration
```python
# Query threat intelligence databases
results = search.query_threat_intelligence(iocs)
```

## Implementation Decisions

### Why Dynamic Discovery?
- **Problem:** 24+ agents managed manually would be brittle
- **Solution:** Scan filesystem at runtime
- **Benefit:** Add agents without code changes, scales easily

### Why Agent Messaging?
- **Problem:** Sequential processing would lose collaborative insight
- **Solution:** Agents can query each other and cross-reference
- **Benefit:** Complex investigations benefit from agent collaboration

### Why NEXUS Orchestration?
- **Problem:** Agent teams could work inefficiently without coordination
- **Solution:** Strategic master commander allocates resources
- **Benefit:** Optimal investigation path for each threat type

### Why Phase-Based Investigation?
- **Problem:** All threats don't require same analysis steps
- **Solution:** NEXUS selects phases based on threat classification
- **Benefit:** Efficient, targeted investigation workflow

### Why Confidence Metrics?
- **Problem:** Finding aggregation loses certainty information
- **Solution:** Track confidence per agent per finding
- **Benefit:** Executive can assess evidence strength

## Performance Optimization

### Agent Discovery (100ms)
```python
# Optimize: Cache agent list between invocations
@lru_cache
def discover_all_agents():
    # Scan filesystem once, cache results
    pass
```

### Message Routing (<1ms)
```python
# Optimize: Hash-based agent lookup
agent_lookup = {name: agent for name, agent in agents.items()}
```

### Synthesis (Variable)
```python
# Optimize: Parallel agent analysis
# Consider ThreadPoolExecutor for independent agent tasks
```

## Testing Strategy

### Unit Tests
```python
def test_agent_discovery():
    agents = discover_all_agents()
    assert len(agents) > 0
    assert all("found" in attr for attr in agent_attributes)

def test_message_routing():
    msg = agent1.send_message(agent2, "query", "content")
    agent2.receive_message(msg)
    assert msg in agent2.message_inbox

def test_query_classification():
    result = nexus.parse_query("ransomware attack")
    assert result["threat_level"] == "critical"
    assert "malware" in result["investigation_scope"]
```

### Integration Tests
```python
def test_complete_investigation():
    investigation = ui.investigate_query("Check suspicious IP")
    assert investigation["delegation_plan"]
    assert investigation["synthesis"]
    assert investigation["synthesis"]["threat_assessment"]
```

### Mock Tests
```python
def test_synthetic_investigation():
    # Populate AgentContext with mock findings
    # Run synthesis
    # Assert narrative construction
```

## Monitoring & Debugging

### Investigation Logging
```python
nexus.investigation_log
# Sample:
[
    "NEXUS: Initiating investigation - Check IP",
    "Classification: threat_level=high",
    "Delegation: Investigation Division (3 agents)",
    "[CRITICAL] C2 communication detected"
]
```

### Agent Status
```python
agent.to_dict()
# Returns:
{
    "name": "REAPER",
    "division": "Investigation",
    "findings": {...},
    "confidence": 0.95,
    "messages_sent": 3,
    "messages_received": 2
}
```

### Message Tracking
```python
agent.message_inbox      # Received messages
agent.message_outbox     # Sent messages
context.message_queue    # Pending messages
context.message_history  # By sender
```

## Security Considerations

1. **Input Validation**
   - Validate all user queries
   - Escaped data in system prompts

2. **Agent Isolation**
   - Each agent maintains separate state
   - No direct filesystem access

3. **Message Integrity**
   - Timestamped messages
   - Context tracking for audit trail

4. **Output Sanitization**
   - Escape findings for display
   - Filter sensitive data before synthesis

## Scalability Roadmap

### Phase 1 (Current): Core System
- ✅ 24+ agents
- ✅ Dynamic discovery
- ✅ Inter-agent messaging
- ✅ NEXUS orchestration

### Phase 2 (Future): Advanced Collaboration
- Multi-round investigation cycles
- Agent learning from past cases
- Reputation-based agent specialization
- Dynamic team sizing based on threat

### Phase 3 (Future): Data Integration
- Real-time data streaming
- Persistent investigation repository
- Cross-investigation pattern detection
- Automated threat feed integration

### Phase 4 (Future): ML Enhancement
- Agent capability profiling
- Optimal team prediction
- Threat pattern clustering
- Confidence calibration

## Future Enhancements

1. **Parallel Investigation**
   ```python
   # Run multiple phases simultaneously
   ThreadPoolExecutor for parallel agent analysis
   ```

2. **Agent Learning**
   ```python
   # Agents save findings for future reference
   investigation_repository.save(findings)
   ```

3. **Advanced Synthesis**
   ```python
   # Machine learning for pattern detection
   ml_model.analyze_findings()
   ```

4. **Real-time Monitoring**
   ```python
   # WebSocket interface for live investigation
   # Real-time agent status updates
   ```

5. **Multi-Query Correlation**
   ```python
   # Link related investigations
   # Cross-case threat actor tracking
   ```

## Conclusion

The Robin multi-agent system provides a scalable, extensible architecture for sophisticated threat intelligence gathering and analysis. Key innovations:

- **Dynamic Agent Discovery** - Add agents without code changes
- **Strategic Orchestration** - NEXUS makes authoritative decisions
- **Collaborative Investigation** - Agents work together on complex threats
- **Evidence-Based Decision Making** - Confidence metrics throughout
- **Executive-Level Reporting** - Polished threat intelligence synthesis

This architecture enables Robin to grow from 24+ agents to hundreds while maintaining operational efficiency and finding quality.
