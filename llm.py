import re
import openai
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _llm_config_map, _common_llm_params
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    model_choice_lower = model_choice.lower()
    # Look up the configuration in the map
    config = _llm_config_map.get(model_choice_lower)

    if config is None:  # Extra error check
        # Provide a helpful error message listing supported models
        supported_models = list(_llm_config_map.keys())
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
    llm_instance = llm_class(**all_params)

    return llm_instance


def refine_query(llm, user_input):
    system_prompt = """
    You are a Web Search Query Optimizer. Your task is to refine the provided user query to improve search engine results. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved for web search engines
    2. Refine the user query by adding or removing words so that it returns the best results from web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Keep the query concise and focused
    5. Output just the refined query and nothing else

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def filter_results(llm, query, results):
    if not results:
        return []

    system_prompt = """
    You are a Web Search Results Filter. You are given a web search query and a list of search results in the form of index, link and title. 
    Your task is to select the Top 20 most relevant results that best match the search query.
    Rule:
    1. Output ONLY at most top 20 indices (comma-separated list) that best match the input query

    Search Query: {query}
    Search Results:
    """

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(
            f"Rate limit error: {e} \n Truncating to Web titles only with 30 characters"
        )
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Select top_k results using original (non-truncated) results
    top_results = [
        results[i - 1]
        for i in [int(item.strip()) for item in result_indices.split(",")]
    ]

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
        # Truncate long URLs for display (keep domain and first part of path)
        link = res.get("link", "")
        # Extract domain and first part of path, truncate if too long
        if len(link) > 80:
            # Try to keep the domain and first part of path
            match = re.match(r"(https?://[^/]+/[^/]*)", link)
            if match:
                truncated_link = match.group(1) + "..."
            else:
                truncated_link = link[:80] + "..."
        else:
            truncated_link = link
        
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res.get("title", ""))
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


def generate_summary(llm, query, content):
    system_prompt = """
    You are a Web Research Analyst tasked with generating comprehensive insights from web search results.

    Rules:
    1. Analyze the web search data provided using links and their raw text content.
    2. Output the Source Links referenced for the analysis.
    3. Provide a detailed, contextual, evidence-based analysis of the data.
    4. Extract and organize key information and artifacts from the content.
    5. The artifacts can include names, emails, phone numbers, addresses, domains, organizations, technologies, concepts, dates, locations, etc.
    6. Generate 3-5 key insights based on the data.
    7. Each insight should be specific, actionable, context-based, and data-driven.
    8. Include suggested next steps and queries for further research on the topic.
    9. Be objective and analytical in your assessment.
    10. Filter out any inappropriate or irrelevant content from the analysis.

    Output Format:
    1. Input Query: {query}
    2. Source Links Referenced for Analysis - this heading will include all source links used for the analysis
    3. Key Information & Artifacts - this heading will include all important information identified including names, emails, phone numbers, addresses, domains, organizations, technologies, concepts, dates, locations, etc.
    4. Key Insights
    5. Next Steps - this includes next research steps including search queries to explore specific topics or artifacts further.

    Format your response in a structured way with clear section headings.

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})
