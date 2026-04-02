># Robin Multi-Agent Threat Intelligence System

## Overview

Robin now operates as a **coordinated multi-agent investigation team** capable of deep, specialized dark web threat analysis. When Multi-Agent Mode is enabled, up to 8 specialized agents deploy in coordinated sequence to dissect threats from multiple forensic, financial, temporal, and attribution angles.

## Available Agents

### Investigation Division (8 Specialized Agents)

1. **REAPER — Threat Hunter**
   - Role: Proactive threat hunting and hypothesis-driven analysis
   - Searches for persistence mechanisms, behavioral anomalies, and TTPs
   - Output: Threat hunting hypotheses and suspicious patterns

2. **TRACE — Digital Forensics Investigator**
   - Role: Evidence extraction and chain-of-custody forensics
   - Extracts file system artifacts, timestamps, deleted items
   - Output: Forensic artifacts with confidence levels

3. **LEDGER — Blockchain Investigator**
   - Role: Cryptocurrency transaction tracing and payment flow analysis
   - Traces wallet clusters, ransomware payments, DeFi exploits
   - Output: Cryptocurrency IOCs and transaction pathways

4. **FLUX — Log & Timeline Expert**
   - Role: Timeline reconstruction from disparate log sources
   - Correlates events across syslog, Windows Event Log, firewall logs
   - Output: Chronological incident timeline with source attribution

5. **MASON — Incident Response Investigator**
   - Role: IR lifecycle framework and breach investigation
   - Structures findings within Preparation → Detection → Containment → Eradication → Recovery
   - Output: Structured IR report with root cause and remediation

6. **VEIL — Dark Web Researcher**
   - Role: Dark web ecosystem context and market structure analysis
   - References academic papers, journalism, and public threat reports
   - Output: Dark web ecosystem insights and forum dynamics

7. **BISHOP — Attribution Analyst**
   - Role: Threat actor attribution with confidence levels
   - Assesses means, motive, opportunity for attribution
   - Output: Attribution assessment with confidence (High/Medium/Low)

8. **GHOST — Undercover Intelligence Researcher**
   - Role: Behavioral profiling and social network analysis
   - Maps threat actor personas, communication patterns, group structures
   - Output: Threat actor behavioral profiles and social graphs

## Multi-Agent Workflow

### Investigation Pipeline

```
Search & Scrape (standard) 
    ↓
REAPER (Threat Hunting) 
    ↓
TRACE (Forensics) 
    ↓
LEDGER (Payment Tracing) 
    ↓
FLUX (Timeline) 
    ↓
MASON (Incident Response) 
    ↓
VEIL (Dark Web Context) 
    ↓
BISHOP (Attribution) 
    ↓
GHOST (Behavioral Profiling) 
    ↓
INTEGRATED MULTI-AGENT REPORT
```

### Key Features

1. **Sequential Agent Deployment**
   - Each agent builds on prior findings
   - Context shared across all agents
   - Evidence accumulated in unified investigation record

2. **Specialized Expertise**
   - Each agent maintains personality and role boundaries
   - No generic "summarize everything" prompt
   - High-confidence findings due to focused analysis

3. **Multi-Dimensional Analysis**
   - Forensic (TRACE)
   - Financial (LEDGER)
   - Temporal (FLUX)
   - Operational (MASON, VEIL)
   - Attribution (BISHOP, GHOST)
   - Hunting (REAPER)

4. **Confidence Tracking**
   - Each agent explicitly states confidence levels
   - Findings tagged by source agent
   - Attribution confidence framework applied

5. **Integrated Final Report**
   - Synthesizes all agent findings
   - Cross-referenced evidence chains
   - Clear attribution pathway documented

## Using Multi-Agent Mode

### UI Controls

In the sidebar under "Investigation Workflow Settings":

- **🔬 Multi-Agent Investigation Mode** (toggle)
  - Enables specialized 8-agent team
  - Disabled by default (standard dual-output mode)

- **Deep Research Search** (toggle)
  - Works with both standard and multi-agent modes
  - Recursively crawls onion links from search results

- **Deep Crawl Depth** (slider, 0-2)
  - Controls recursive frontier expansion
  - Higher values increase coverage and runtime

### Running a Multi-Agent Investigation

1. Enter your dark web search query
2. Enable "🔬 Multi-Agent Investigation Mode" in sidebar
3. Optionally: Enable "Deep Research Search" and set crawl depth
4. Click "Run"
5. Monitor agent progress in real-time
6. Review individual agent findings in expandable cards
7. Read integrated multi-agent final report

### Output

Multi-agent investigations produce:

1. **Per-Agent Findings** (expandable cards)
   - Each agent's specialized analysis
   - High-confidence claims with supporting evidence
   - Recommendations for further investigation

2. **Integrated Report**
   - Cross-referenced findings from all 8 agents
   - Unified threat narrative
   - Complete forensic, financial, temporal, and attribution story

3. **Workflow Timeline**
   - Agent execution sequence with timestamps
   - Success/failure status per agent
   - Cumulative processing time

4. **Session Persistence**
   - Investigation saved with all agent findings
   - Queryable session history
   - Downloadable multi-agent report

## Comparison: Standard vs Multi-Agent Mode

### Standard Dual-Output Mode
- Single LLM generates Filtered + Risky summaries
- Fast (parallel filtered/risky generation)
- General-purpose threat analysis
- Good for quick reconnaissance

### Multi-Agent Mode
- 8 specialized agents in sequence
- Slower but much more detailed
- Deep forensic, financial, temporal, attribution analysis
- Ideal for complex investigations requiring specialized expertise
- Higher confidence due to focused agent roles
- Better chain-of-custody documentation

## Security & Safety Implications

### Input Sanitization
- All scraped data sanitized before agent use
- Prompt injection attack patterns removed
- Control characters and malicious sequences stripped

### Agent Boundaries
- Each agent has strict personality and role constraints
- Agents cannot override system instructions
- Evidence-based analysis enforced

### Filtering & Safe Mode
- Multi-agent reports can be used in standard reporting
- No built-in "filtered" mode for multi-agent yet (future enhancement)
- All findings timestamped and sourced

## Example Investigation Scenario

### Query: "ransomware actor payment infrastructure"

**REAPER** → Identifies hypothesis: "Activity correlates with known RaaS group based on behavioral patterns"

**TRACE** → Extracts file artifacts: "Host infection artifacts show persistence mechanisms X, Y, Z from MITRE ATT&CK"

**LEDGER** → Traces payments: "Bitcoin wallet cluster ABC receives 0.5 BTC from 47 known ransomware payment addresses"

**FLUX** → Builds timeline: "T+0: Initial compromise via phishing. T+4h: Lateral movement. T+24h: Data exfiltration. T+36h: Ransom demand delivered"

**MASON** → IR assessment: "Contained within 6 hours. Root cause: unpatched CVE-XXXX-XXXXX. Affected systems: 12 workstations + 2 servers"

**VEIL** → Dark web context: "Actor advertises on forum XYZ using alias 'FROSTBITE'. Known associates include 5 other RaaS operators"

**BISHOP** → Attribution: "HIGH confidence: FIN11 ransomware group. Motive: financial. Means: known TTPs. Opportunity: unpatched systems"

**GHOST** → Profiling: "Group structure: 1 leader, 3 core operators, ~12 affiliates. Communication: Jabber + forums. OpSec: moderate (some OPSEC failures)"

**FINAL REPORT** → Comprehensive 8-agent consensus with evidence pathways for each claim

## Architecture

### Components

- `agents.py` — Agent class, personality loading, rosters
- `agent_orchestrator.py` — Multi-agent workflow orchestration
- `ui.py` — Streamlit UI with multi-agent mode toggle
- `Agents/Investigation Division/` — Agent personality files

### Data Flow

```
User Query 
    ↓
Search & Scrape (standard pipeline)
    ↓
Orchestrator.initialize_context()
    ↓
for each agent in [REAPER, TRACE, LEDGER, FLUX, MASON, VEIL, BISHOP, GHOST]:
    orchestrator.run_agent_task()
    ↓
Orchestrator._synthesize_findings()
    ↓
Integrated Report + Per-Agent Findings
    ↓
Save Investigation + Session History
```

## Future Enhancements

1. **Specialist Teams** 
   - Separate team rosters for malware analysis, fraud, OSINT, etc.
   - Config-driven team selection

2. **Filtered Multi-Agent Mode**
   - Safety-focused agent team for customer delivery
   - Automated redaction per agent role

3. **Agent Voting**
   - Consensus mechanism for attribution confidence
   - Conflict resolution framework

4. **Parallel Agent Execution**
   - Independent agents run in parallel where possible
   - Intelligent dependency management

5. **Custom Agents**
   - Load user-defined agent personalities
   - Extend roster with domain-specific roles (HIPAA, PCI, CIS-specific)

---

**Version:** Multi-Agent v1.0 (Robin 2.0)  
**Status:** Production Ready  
**Last Updated:** 2 April 2026
