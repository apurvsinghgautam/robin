"""Specialized sub-agents for Robin OSINT investigations."""
import asyncio
from dataclasses import dataclass
from typing import Optional

import anthropic

from .prompts import SUBAGENT_PROMPTS, SUBAGENT_DESCRIPTIONS
from config import DEFAULT_MODEL


@dataclass
class SubAgentResult:
    """Result from a sub-agent analysis."""
    agent_type: str
    analysis: str
    success: bool
    error: Optional[str] = None


class SubAgent:
    """
    Base class for specialized analysis sub-agents.

    Sub-agents are lightweight, focused analysts that receive
    content from the main RobinAgent and return specialized analysis.
    """

    def __init__(
        self,
        agent_type: str,
        model: Optional[str] = None,
    ):
        """
        Initialize a sub-agent.

        Args:
            agent_type: One of ThreatActorProfiler, IOCExtractor,
                       MalwareAnalyst, MarketplaceInvestigator
            model: Claude model to use (defaults to config)
        """
        if agent_type not in SUBAGENT_PROMPTS:
            raise ValueError(f"Unknown agent type: {agent_type}. "
                           f"Valid types: {list(SUBAGENT_PROMPTS.keys())}")

        self.agent_type = agent_type
        self.model = model or DEFAULT_MODEL
        self.system_prompt = SUBAGENT_PROMPTS[agent_type]
        self.description = SUBAGENT_DESCRIPTIONS[agent_type]
        self._client = anthropic.Anthropic()

    async def analyze(self, content: str, context: str = "") -> SubAgentResult:
        """
        Analyze content and return specialized analysis.

        Args:
            content: The scraped content to analyze
            context: Additional context (e.g., original query)

        Returns:
            SubAgentResult with the analysis
        """
        # Build the prompt for the sub-agent
        prompt = f"""## Investigation Context
{context}

## Content to Analyze
{content}

Please analyze the above content according to your specialty."""

        try:
            # Run synchronous API call in executor to not block
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}]
                )
            )

            # Extract text from response
            full_response = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    full_response += block.text

            return SubAgentResult(
                agent_type=self.agent_type,
                analysis=full_response,
                success=True,
            )
        except Exception as e:
            return SubAgentResult(
                agent_type=self.agent_type,
                analysis="",
                success=False,
                error=str(e),
            )


class ThreatActorProfiler(SubAgent):
    """Specialized agent for threat actor profiling."""

    def __init__(self, model: Optional[str] = None):
        super().__init__("ThreatActorProfiler", model)


class IOCExtractor(SubAgent):
    """Specialized agent for extracting indicators of compromise."""

    def __init__(self, model: Optional[str] = None):
        super().__init__("IOCExtractor", model)


class MalwareAnalyst(SubAgent):
    """Specialized agent for malware analysis."""

    def __init__(self, model: Optional[str] = None):
        super().__init__("MalwareAnalyst", model)


class MarketplaceInvestigator(SubAgent):
    """Specialized agent for marketplace investigation."""

    def __init__(self, model: Optional[str] = None):
        super().__init__("MarketplaceInvestigator", model)


# =============================================================================
# SUB-AGENT ORCHESTRATION
# =============================================================================

async def run_subagent(
    agent_type: str,
    content: str,
    context: str = "",
    model: Optional[str] = None,
) -> SubAgentResult:
    """
    Run a single sub-agent analysis.

    Args:
        agent_type: Type of sub-agent to run
        content: Content to analyze
        context: Additional context
        model: Optional model override

    Returns:
        SubAgentResult with analysis
    """
    agent = SubAgent(agent_type, model)
    return await agent.analyze(content, context)


async def run_subagents_parallel(
    agent_types: list[str],
    content: str,
    context: str = "",
    model: Optional[str] = None,
) -> list[SubAgentResult]:
    """
    Run multiple sub-agents in parallel.

    Args:
        agent_types: List of agent types to run
        content: Content to analyze
        context: Additional context
        model: Optional model override

    Returns:
        List of SubAgentResults
    """
    tasks = [
        run_subagent(agent_type, content, context, model)
        for agent_type in agent_types
    ]
    return await asyncio.gather(*tasks)


def get_available_subagents() -> dict[str, str]:
    """Return available sub-agent types and their descriptions."""
    return SUBAGENT_DESCRIPTIONS.copy()
