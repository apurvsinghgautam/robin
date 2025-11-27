"""
LLM integration module for query refinement, result filtering, and summary generation.
"""

import logging
import re
from typing import Dict, List, Any

import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from constants import MAX_FILTERED_RESULTS

logger = logging.getLogger(__name__)


def get_llm(model_choice: str) -> Any:
    """
    Initialize and return an LLM instance based on the model choice.

    Args:
        model_choice: The name of the model to use

    Returns:
        Configured LLM instance

    Raises:
        ValueError: If the model is not supported
    """
    config = resolve_model_config(model_choice)

    if config is None:
        supported_models = get_model_choices()
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters
    all_params = {**_common_llm_params, **model_specific_params}

    return llm_class(**all_params)


def refine_query(llm: Any, user_input: str) -> str:
    """
    Refine a user query for better dark web search results.

    Args:
        llm: The LLM instance to use
        user_input: The original user query

    Returns:
        Refined search query
    """
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines.

    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Output just the user query and nothing else

    INPUT:
    """
    prompt_template = ChatPromptTemplate([
        ("system", system_prompt),
        ("user", "{query}")
    ])
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def filter_results(
    llm: Any,
    query: str,
    results: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    Filter search results to keep only the most relevant ones.

    Args:
        llm: The LLM instance to use
        query: The search query
        results: List of search result dictionaries

    Returns:
        Filtered list of relevant results
    """
    if not results:
        return []

    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. You are given a dark web search query and a list of search results in the form of index, link and title.
    Your task is select the Top 20 relevant results that best match the search query for user to investigate more.
    Rule:
    1. Output ONLY atmost top 20 indices (comma-separated list) no more than that that best match the input query

    Search Query: {query}
    Search Results:
    """

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate([
        ("system", system_prompt),
        ("user", "{results}")
    ])
    chain = prompt_template | llm | StrOutputParser()

    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        logger.warning(f"Rate limit error: {e}. Truncating to web titles only.")
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Parse indices from LLM response
    parsed_indices = []
    for match in re.findall(r"\d+", result_indices):
        try:
            idx = int(match)
            if 1 <= idx <= len(results):
                parsed_indices.append(idx)
        except ValueError:
            continue

    # Remove duplicates while preserving order
    seen: set = set()
    parsed_indices = [i for i in parsed_indices if not (i in seen or seen.add(i))]

    if not parsed_indices:
        logger.warning(
            "Unable to interpret LLM result selection ('%s'). "
            "Defaulting to the top %s results.",
            result_indices,
            min(len(results), MAX_FILTERED_RESULTS),
        )
        parsed_indices = list(range(1, min(len(results), MAX_FILTERED_RESULTS) + 1))

    top_results = [results[i - 1] for i in parsed_indices[:MAX_FILTERED_RESULTS]]
    logger.info(f"Filtered to {len(top_results)} relevant results")

    return top_results


def _generate_final_string(
    results: List[Dict[str, str]],
    truncate: bool = False
) -> str:
    """
    Generate a formatted string from the search results for LLM processing.

    Args:
        results: List of search result dictionaries
        truncate: Whether to truncate titles and links for rate limit handling

    Returns:
        Formatted string of results
    """
    max_title_length = 30 if truncate else None
    max_link_length = 0 if truncate else None

    final_str = []
    for i, res in enumerate(results):
        truncated_link = re.sub(r"(?<=\.onion).*", "", res["link"])
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res["title"])

        if truncated_link == "" and title == "":
            continue

        if truncate:
            if max_title_length and len(title) > max_title_length:
                title = title[:max_title_length] + "..."
            if max_link_length is not None and len(truncated_link) > max_link_length:
                truncated_link = truncated_link[:max_link_length] + "..." if max_link_length > 0 else ""

        final_str.append(f"{i+1}. {truncated_link} - {title}")

    return "\n".join(final_str)


def generate_summary(
    llm: Any,
    query: str,
    content: Dict[str, str]
) -> str:
    """
    Generate an intelligence summary from scraped dark web content.

    Args:
        llm: The LLM instance to use
        query: The original search query
        content: Dictionary mapping URLs to scraped content

    Returns:
        Formatted intelligence summary
    """
    system_prompt = """
    You are an Cybercrime Threat Intelligence Expert tasked with generating context-based technical investigative insights from dark web osint search engine results.

    Rules:
    1. Analyze the Darkweb OSINT data provided using links and their raw text.
    2. Output the Source Links referenced for the analysis.
    3. Provide a detailed, contextual, evidence-based technical analysis of the data.
    4. Provide intellgience artifacts along with their context visible in the data.
    5. The artifacts can include indicators like name, email, phone, cryptocurrency addresses, domains, darkweb markets, forum names, threat actor information, malware names, TTPs, etc.
    6. Generate 3-5 key insights based on the data.
    7. Each insight should be specific, actionable, context-based, and data-driven.
    8. Include suggested next steps and queries for investigating more on the topic.
    9. Be objective and analytical in your assessment.
    10. Ignore not safe for work texts from the analysis

    Output Format:
    1. Input Query: {query}
    2. Source Links Referenced for Analysis - this heading will include all source links used for the analysis
    3. Investigation Artifacts - this heading will include all technical artifacts identified including name, email, phone, cryptocurrency addresses, domains, darkweb markets, forum names, threat actor information, malware names, etc.
    4. Key Insights
    5. Next Steps - this includes next investigative steps including search queries to search more on a specific artifacts for example or any other topic.

    Format your response in a structured way with clear section headings.

    INPUT:
    """
    prompt_template = ChatPromptTemplate([
        ("system", system_prompt),
        ("user", "{content}")
    ])
    chain = prompt_template | llm | StrOutputParser()

    logger.info(f"Generating summary for query: {query}")
    return chain.invoke({"query": query, "content": content})
