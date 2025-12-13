import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY
from logger_utils import get_logger
import logging
import re

import warnings

warnings.filterwarnings("ignore")

# Initialize logger
logger = get_logger()


def get_llm(model_choice):
    # Look up the configuration (cloud or local Ollama)
    config = resolve_model_config(model_choice)

    if config is None:  # Extra error check
        supported_models = get_model_choices()
        logger.error(f"Unsupported LLM model: '{model_choice}'. Supported: {', '.join(supported_models)}")
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    # Extract the necessary information from the configuration
    llm_class = config["class"]
    model_specific_params = config["constructor_params"]

    # Combine common parameters with model-specific parameters
    # Model-specific parameters will override common ones if there are any conflicts
    all_params = {**_common_llm_params, **model_specific_params}

    # Create the LLM instance using the gathered parameters
    logger.info(f"Initializing LLM model: {model_choice} (Class: {llm_class.__name__})")
    llm_instance = llm_class(**all_params)
    
    # Store model name for logging
    llm_instance._robin_model_name = model_choice

    return llm_instance


def refine_query(llm, user_input, model_name: str = "unknown"):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Output just the user query and nothing else

    INPUT:
    """
    
    # Log API call with data preview
    full_prompt = f"System: {system_prompt}\nUser: {user_input}"
    logger.log_api_call(
        model=model_name,
        stage="Query Refinement",
        prompt_type="refine_query",
        data_preview=full_prompt,
        data_length=len(full_prompt)
    )
    
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    logger.info(f"Refining query: '{user_input}'")
    result = chain.invoke({"query": user_input})
    logger.info(f"Refined query result: '{result}'")
    return result


def filter_results(llm, query, results, model_name: str = "unknown"):
    if not results:
        logger.info("No results to filter")
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
    
    # Log API call with data preview
    full_prompt = f"System: {system_prompt}\nQuery: {query}\nResults: {final_str[:500]}..."
    logger.log_api_call(
        model=model_name,
        stage="Result Filtering",
        prompt_type="filter_results",
        data_preview=full_prompt,
        data_length=len(final_str)
    )
    
    logger.info(f"Filtering {len(results)} results for query: '{query}'")

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
        logger.info(f"Filtering completed, received indices: {result_indices[:100]}")
    except openai.RateLimitError as e:
        print(
            f"Rate limit error: {e} \n Truncating to Web titles only with 30 characters"
        )
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Select top_k results using original (non-truncated) results
    parsed_indices = []
    for match in re.findall(r"\d+", result_indices):
        try:
            idx = int(match)
            if 1 <= idx <= len(results):
                parsed_indices.append(idx)
        except ValueError:
            continue

    # Remove duplicates while preserving order
    seen = set()
    parsed_indices = [
        i for i in parsed_indices if not (i in seen or seen.add(i))
    ]

    if not parsed_indices:
        logger.warning(
            f"Unable to interpret LLM result selection ('{result_indices}'). "
            f"Defaulting to the top {min(len(results), 20)} results."
        )
        parsed_indices = list(range(1, min(len(results), 20) + 1))

    top_results = [results[i - 1] for i in parsed_indices[:20]]
    logger.info(f"Selected {len(top_results)} filtered results")

    return top_results


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        # Use only the first 35 characters of the title
        max_title_length = 30
        # Do not use link at all
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        # Truncate link at .onion for display
        truncated_link = re.sub(r"(?<=\.onion).*", "", res["link"])
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res["title"])
        if truncated_link == "" and title == "":
            continue

        if truncate:
            # Truncate title to max_title_length characters
            title = (
                title[:max_title_length] + "..."
                if len(title) > max_title_length
                else title
            )
            # Truncate link to max_link_length characters
            truncated_link = (
                truncated_link[:max_link_length] + "..."
                if len(truncated_link) > max_link_length
                else truncated_link
            )

        final_str.append(f"{i+1}. {truncated_link} - {title}")

    return "\n".join(s for s in final_str)


def generate_summary(llm, query, content, model_name: str = "unknown"):
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
    
    # Log API call with data preview
    content_preview = str(content)[:500] if content else "No content"
    full_prompt = f"System: {system_prompt}\nQuery: {query}\nContent: {content_preview}..."
    content_length = len(str(content)) if content else 0
    logger.log_api_call(
        model=model_name,
        stage="Summary Generation",
        prompt_type="generate_summary",
        data_preview=full_prompt,
        data_length=content_length
    )
    
    logger.info(f"Generating summary for query: '{query}' with {len(content) if isinstance(content, dict) else 'N/A'} content items")
    
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    result = chain.invoke({"query": query, "content": content})
    logger.info(f"Summary generation completed, length: {len(result)} characters")
    return result
