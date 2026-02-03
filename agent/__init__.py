"""Robin Agent SDK module."""
from .client import RobinAgent, InvestigationResult, run_investigation
from .tools import TOOL_DEFINITIONS, execute_tool, darkweb_search, darkweb_scrape, save_report, delegate_analysis
from .prompts import (
    ROBIN_SYSTEM_PROMPT,
    SUBAGENT_PROMPTS,
    SUBAGENT_DESCRIPTIONS,
)
from .subagents import (
    SubAgent,
    SubAgentResult,
    ThreatActorProfiler,
    IOCExtractor,
    MalwareAnalyst,
    MarketplaceInvestigator,
    run_subagent,
    run_subagents_parallel,
    get_available_subagents,
)

__all__ = [
    # Main agent
    "RobinAgent",
    "InvestigationResult",
    "run_investigation",
    # Tools
    "darkweb_search",
    "darkweb_scrape",
    "save_report",
    "delegate_analysis",
    # Prompts
    "ROBIN_SYSTEM_PROMPT",
    "SUBAGENT_PROMPTS",
    "SUBAGENT_DESCRIPTIONS",
    # Sub-agents
    "SubAgent",
    "SubAgentResult",
    "ThreatActorProfiler",
    "IOCExtractor",
    "MalwareAnalyst",
    "MarketplaceInvestigator",
    "run_subagent",
    "run_subagents_parallel",
    "get_available_subagents",
]
