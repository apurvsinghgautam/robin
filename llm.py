import re
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from llm_utils import _llm_config_map, _common_llm_params

import warnings
warnings.filterwarnings("ignore")


# --- Pydantic Models for Structured Output ---
class SearchResultIndices(BaseModel):
    indices: List[int] = Field(description="List of integer indices of the relevant search results")


def get_llm(model_choice):
    model_choice_lower = model_choice.lower()
    config = _llm_config_map.get(model_choice_lower)

    if config is None:
        supported_models = list(_llm_config_map.keys())
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models are: {', '.join(supported_models)}"
        )

    llm_class = config["class"]
    model_specific_params = config["constructor_params"]
    all_params = {**_common_llm_params, **model_specific_params}
    
    return llm_class(**all_params)


def refine_query(llm, user_input):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Refine the user query for dark web search engines.
    Rules:
    1. Remove stopwords and unnecessary conversational text.
    2. Focus on keywords specific to dark web markets, forums, and leaks.
    3. Do NOT use boolean operators (AND, OR) as many dark web engines don't support them.
    4. Output ONLY the refined query string.
    """
    prompt_template = ChatPromptTemplate([
        ("system", system_prompt),
        ("user", "{query}")
    ])
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def filter_results(llm, query, results):
    if not results:
        return []

    # Use structured output parser to avoid parsing errors
    parser = JsonOutputParser(pydantic_object=SearchResultIndices)

    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert.
    Select the top 15 most relevant results for the query.
    Return the output as a JSON object with a key 'indices' containing a list of integers.
    Example: {{ "indices": [1, 5, 8] }}
    
    {format_instructions}
    """

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate([
        ("system", system_prompt),
        ("user", "Query: {query}\n\nSearch Results:\n{results}")
    ])
    
    chain = prompt_template | llm | parser

    try:
        response = chain.invoke({
            "query": query, 
            "results": final_str,
            "format_instructions": parser.get_format_instructions()
        })
        
        # Robustly extract indices
        indices = response.get("indices", [])
        
        # Validate indices are within range
        valid_indices = [i for i in indices if 0 < i <= len(results)]
        
        # Map back to original result objects
        top_results = [results[i - 1] for i in valid_indices]
        return top_results

    except Exception as e:
        # Fallback: If LLM fails to parse, return top 5 raw results
        print(f"Filtering failed ({e}). Returning top 5 results.")
        return results[:5]


def _generate_final_string(results, truncate=False):
    final_str = []
    max_title = 30 if truncate else 100
    
    for i, res in enumerate(results):
        # Clean title
        title = re.sub(r"[^0-9a-zA-Z\-\.]", " ", res.get("title", ""))
        title = " ".join(title.split()) # remove extra whitespace
        
        # Truncate link for display
        link = res.get("link", "")
        short_link = link.split(".onion")[0] + ".onion" if ".onion" in link else link
        
        display_text = f"{i+1}. {short_link} - {title[:max_title]}"
        final_str.append(display_text)

    return "\n".join(final_str)


def generate_summary(llm, query, content):
    """
    Generates a summary. Implements Map-Reduce for large content.
    """
    # Convert dict content to a single string if it isn't already
    if isinstance(content, dict):
        full_text = "\n\n".join([f"Source: {k}\nContent: {v}" for k, v in content.items()])
    else:
        full_text = str(content)

    # If content is manageable, do direct summary
    if len(full_text) < 15000:
        return _generate_direct_summary(llm, query, full_text)
    
    # Otherwise, do Map-Reduce
    return _generate_map_reduce_summary(llm, query, full_text)


def _generate_direct_summary(llm, query, content):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert.
    Analyze the provided dark web search results and generate a technical intelligence report.
    
    Structure:
    1. Input Query
    2. Source Links Referenced
    3. Investigation Artifacts (Extract: emails, BTC addresses, domains, handles, malware names)
    4. Key Insights (3-5 specific, actionable points)
    5. Next Steps
    
    Ignore NSFW content. Be objective.
    """
    prompt = ChatPromptTemplate([("system", system_prompt), ("user", "Query: {query}\n\nData:\n{content}")])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})


def _generate_map_reduce_summary(llm, query, full_text):
    """
    Splits text, summarizes chunks, then summarizes the summaries.
    """
    # Simple chunking by character count
    chunk_size = 12000
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    # MAP STEP: Summarize each chunk
    map_prompt = ChatPromptTemplate([
        ("system", "Summarize the technical artifacts and key info from this dark web data specifically related to: {query}."),
        ("user", "{chunk}")
    ])
    map_chain = map_prompt | llm | StrOutputParser()
    
    summaries = []
    for chunk in chunks:
        try:
            s = map_chain.invoke({"query": query, "chunk": chunk})
            summaries.append(s)
        except Exception:
            continue
            
    combined_summaries = "\n---\n".join(summaries)
    
    # REDUCE STEP: Final Report
    reduce_system_prompt = """
    You are a Cybercrime Threat Intelligence Expert.
    I have analyzed a large dataset in chunks. Below are the summaries of those chunks.
    Combine them into one final, coherent technical intelligence report.
    
    Structure:
    1. Input Query
    2. Key Insights (Synthesized from all chunks)
    3. Investigation Artifacts (Aggregated)
    4. Next Steps
    """
    reduce_prompt = ChatPromptTemplate([
        ("system", reduce_system_prompt), 
        ("user", "Query: {query}\n\nIntermediate Summaries:\n{summaries}")
    ])
    reduce_chain = reduce_prompt | llm | StrOutputParser()
    
    return reduce_chain.invoke({"query": query, "summaries": combined_summaries})
