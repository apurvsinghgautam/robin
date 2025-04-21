import re
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from config import OPENAI_API_KEY, ANTHROPIC_API_KEY
from langchain_core.prompts import ChatPromptTemplate
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
import openai

import warnings
warnings.filterwarnings("ignore")

class BufferedStreamingHandler(BaseCallbackHandler):
    def __init__(self, buffer_limit: int = 60):
        self.buffer = ""
        self.buffer_limit = buffer_limit

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.buffer += token
        if "\n" in token or len(self.buffer) >= self.buffer_limit:
            print(self.buffer, end="", flush=True)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        if self.buffer:
            print(self.buffer, end="", flush=True)
            self.buffer = ""

def get_llm(model_choice):
    model_choice_lower = model_choice.lower()
    if model_choice_lower in ['gpt4o', 'gpt-4o', 'gpt4']:
        # GPT-4o from OpenAI
        return ChatOpenAI(model_name="gpt-4o", temperature=0, streaming=True, callbacks=[BufferedStreamingHandler(buffer_limit=60)])
    elif model_choice_lower in ['gpt-4.1']:
        # GPT-4o from OpenAI
        return ChatOpenAI(model_name="gpt-4.1", temperature=0, streaming=True, callbacks=[BufferedStreamingHandler(buffer_limit=60)])
    elif model_choice_lower in ['claude sonnet 3.5', 'claude-sonnet-3.5']:
        # Claude Sonnet 3.5 from Anthropic
        return ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0, streaming=True, callbacks=[BufferedStreamingHandler(buffer_limit=60)])
    elif model_choice_lower in ['ollama', 'lamma3.1', 'llama']:
        # Local model via Ollama; adjust the model parameter as needed.
        return ChatOllama(model="llama3.1", temperature=0, streaming=True, callbacks=[BufferedStreamingHandler(buffer_limit=60)])
    else:
        raise ValueError("Unsupported LLM model")

def refine_query(llm, user_input):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Output just the user query and nothing else

    INPUT:
    """
    prompt_template = ChatPromptTemplate([("system", system_prompt), ("user", "{query}")])
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})

def filter_results(llm, query, results):
    if not results:
        return []

    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. You are given a dark web search query and a list of search results in the form of index, link and title. 
    Your task is select the Top 20 relevant results that best match the search query for user to investigate more.
    Rule:
    1. Output only the top 20 indices (comma-separated list) no more than that that best match the input query

    Search Query: {query}
    Search Results:
    """
    
    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate([("system", system_prompt), ("user", "{results}")])
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(f"Rate limit error: {e} \n Truncating to Web titles only with 30 characters")
        final_str = _generate_final_string(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Select top_k results using original (non-truncated) results
    top_results = [results[i-1] for i in [int(item.strip()) for item in result_indices.split(",")]]

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
        truncated_link = re.sub(r'(?<=\.onion).*', '', res['link'])
        title = re.sub(r'[^0-9a-zA-Z\-\.]', ' ', res['title'])
        if truncated_link == '' and title == '':
            continue

        if truncate:
            # Truncate title to max_title_length characters
            title = title[:max_title_length] + '...' if len(title) > max_title_length else title
            # Truncate link to max_link_length characters
            truncated_link = truncated_link[:max_link_length] + '...' if len(truncated_link) > max_link_length else truncated_link 

        final_str.append(f"{i+1}. {truncated_link} - {title}")
    
    return "\n".join(s for s in final_str)

def generate_summary(llm, query, content):
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
    prompt_template = ChatPromptTemplate([("system", system_prompt), ("user", "{content}")])
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": query, "content": content})
