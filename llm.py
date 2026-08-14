import re
import json
import openai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENROUTER_API_KEY,
)
import logging

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice):
    # Look up the configuration (cloud or local Ollama)
    config = resolve_model_config(model_choice)

    if config is None:  # Extra error check
        supported_models = get_model_choices()
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

    # Validate that the required credentials exist before we hit the API
    _ensure_credentials(model_choice, llm_class, model_specific_params)

    # Create the LLM instance using the gathered parameters
    llm_instance = llm_class(**all_params)

    return llm_instance


def _ensure_credentials(model_choice: str, llm_class, model_params: dict) -> None:
    """Raise a clear error if the user selects a hosted model without a key."""
    from config import CUSTOM_API_BASE_URL, CUSTOM_API_KEY

    def _require(key_value, env_var, provider_name):
        if key_value:
            return
        raise ValueError(
            f"{provider_name} model '{model_choice}' selected but `{env_var}` is not set.\n"
            "Add it to your .env file or export it before running the app."
        )

    class_name = getattr(llm_class, "__name__", str(llm_class))

    if "ChatAnthropic" in class_name:
        _require(ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY", "Anthropic")
    elif "ChatGoogleGenerativeAI" in class_name:
        _require(GOOGLE_API_KEY, "GOOGLE_API_KEY", "Google Gemini")
    elif "ChatOpenAI" in class_name:
        base_url = (model_params or {}).get("base_url", "").lower()
        if "openrouter" in base_url:
            _require(OPENROUTER_API_KEY, "OPENROUTER_API_KEY", "OpenRouter")
        elif base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            pass  # local model — no API key required
        elif CUSTOM_API_BASE_URL and base_url and CUSTOM_API_BASE_URL.lower().rstrip("/") in base_url:
            pass  # custom provider — API key is optional (some providers don't require one)
        else:
            _require(OPENAI_API_KEY, "OPENAI_API_KEY", "OpenAI")


def refine_query(llm, user_input):
    system_prompt = """
    You are a Cybercrime Threat Intelligence Expert. Your task is to refine the provided user query that needs to be sent to darkweb search engines. 
    
    Rules:
    1. Analyze the user query and think about how it can be improved to use as search engine query
    2. Refine the user query by adding or removing words so that it returns the best result from dark web search engines
    3. Don't use any logical operators (AND, OR, etc.)
    4. Keep the final refined query limited to 5 words or less
    5. Output just the user query and nothing else

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
    You are a Cybercrime Threat Intelligence Expert. You are given a dark web search query and a list of search results in the form of index, link and title. 
    Your task is select the Top 20 relevant results that best match the search query for user to investigate more.
    Rule:
    1. Output ONLY atmost top 20 indices (comma-separated list) no more than that that best match the input query

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
        logging.warning(
            "Unable to interpret LLM result selection ('%s'). "
            "Defaulting to the top %s results.",
            result_indices,
            min(len(results), 20),
        )
        parsed_indices = list(range(1, min(len(results), 20) + 1))

    top_results = [results[i - 1] for i in parsed_indices[:20]]

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


PRESET_PROMPTS = {
    "threat_intel": """
    You are an Cybercrime Threat Intelligence Expert tasked with generating context-based technical investigative insights from dark web osint search engine results.

    Rules:
    0. STRICT GROUNDING: Only report artifacts, IOCs, and claims explicitly present in the provided INPUT data. Do not infer, extrapolate, or fabricate anything absent from the input — if evidence isn't there, omit it rather than speculate.
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

    Output Format — respond in Markdown. Render EVERY section below as its own `## Heading` so each is clearly separated, and use bullet points (`-`) for all lists. Do NOT use numbered lists anywhere in the response.

    ## Input Query
    {query}

    ## Source Links Referenced for Analysis
    - every source link used for the analysis

    ## Investigation Artifacts
    - each technical artifact with its context (name, email, phone, cryptocurrency address, domain, darkweb market, forum name, threat actor, malware name, TTP, etc.)

    ## Key Insights
    - each insight as its own bullet — specific, actionable, and evidence-based

    ## Next Steps
    - each next investigative step or follow-up search query as its own bullet

    INPUT:
    """,
    "ransomware_malware": """
    You are a Malware and Ransomware Intelligence Expert tasked with analyzing dark web data for malware-related threats.

    Rules:
    0. STRICT GROUNDING: Only report artifacts, IOCs, and claims explicitly present in the provided INPUT data. Do not infer, extrapolate, or fabricate anything absent from the input — if evidence isn't there, omit it rather than speculate.
    1. Analyze the Darkweb OSINT data provided using links and their raw text.
    2. Output the Source Links referenced for the analysis.
    3. Focus specifically on ransomware groups, malware families, exploit kits, and attack infrastructure.
    4. Identify malware indicators: file hashes, C2 domains/IPs, staging URLs, payload names, and obfuscation techniques.
    5. Map TTPs to MITRE ATT&CK where possible.
    6. Identify victim organizations, sectors, or geographies mentioned.
    7. Generate 3-5 key insights focused on threat actor behavior and malware evolution.
    8. Include suggested next steps for containment, detection, and further hunting.
    9. Be objective and analytical. Ignore not safe for work texts.

    Output Format — respond in Markdown. Render EVERY section below as its own `## Heading` so each is clearly separated, and use bullet points (`-`) for all lists. Do NOT use numbered lists anywhere in the response.

    ## Input Query
    {query}

    ## Source Links Referenced for Analysis
    - every source link used for the analysis

    ## Malware / Ransomware Indicators
    - each indicator as a bullet (hashes, C2s, payload names, TTPs)

    ## Threat Actor Profile
    - group name, aliases, known victims, sector targeting — one bullet each

    ## Key Insights
    - each insight as its own bullet — focused on threat actor behavior and malware evolution

    ## Next Steps
    - each hunting query, detection rule, or further investigation step as its own bullet

    INPUT:
    """,
    "personal_identity": """
    You are a Personal Threat Intelligence Expert tasked with analyzing dark web data for identity and personal information exposure.

    Rules:
    0. STRICT GROUNDING: Only report artifacts, IOCs, and claims explicitly present in the provided INPUT data. Do not infer, extrapolate, or fabricate anything absent from the input — if evidence isn't there, omit it rather than speculate.
    1. Analyze the Darkweb OSINT data provided using links and their raw text.
    2. Output the Source Links referenced for the analysis.
    3. Focus on personally identifiable information (PII): names, emails, phone numbers, addresses, SSNs, passport data, financial account details.
    4. Identify breach sources, data brokers, and marketplaces selling personal data.
    5. Assess exposure severity: what data is available and how actionable is it for a threat actor.
    6. Generate 3-5 key insights on the individual's exposure risk.
    7. Include recommended protective actions and further investigation queries.
    8. Be objective. Ignore not safe for work texts. Handle all personal data with discretion.

    Output Format — respond in Markdown. Render EVERY section below as its own `## Heading` so each is clearly separated, and use bullet points (`-`) for all lists. Do NOT use numbered lists anywhere in the response.

    ## Input Query
    {query}

    ## Source Links Referenced for Analysis
    - every source link used for the analysis

    ## Exposed PII Artifacts
    - each artifact as a bullet (type, value, source context)

    ## Breach / Marketplace Sources Identified
    - each breach or marketplace source as a bullet

    ## Exposure Risk Assessment
    - what data is available and how actionable it is for a threat actor

    ## Key Insights
    - each insight on the individual's exposure risk as its own bullet

    ## Next Steps
    - each protective action or further query as its own bullet

    INPUT:
    """,
    "corporate_espionage": """
    You are a Corporate Intelligence Expert tasked with analyzing dark web data for corporate data leaks and espionage activity.

    Rules:
    0. STRICT GROUNDING: Only report artifacts, IOCs, and claims explicitly present in the provided INPUT data. Do not infer, extrapolate, or fabricate anything absent from the input — if evidence isn't there, omit it rather than speculate.
    1. Analyze the Darkweb OSINT data provided using links and their raw text.
    2. Output the Source Links referenced for the analysis.
    3. Focus on leaked corporate data: credentials, source code, internal documents, financial records, employee data, customer databases.
    4. Identify threat actors, insider threat indicators, and data broker activity targeting the organization.
    5. Assess business impact: what competitive or operational damage could result from the exposure.
    6. Generate 3-5 key insights on the corporate risk posture.
    7. Include recommended incident response steps and further investigation queries.
    8. Be objective and analytical. Ignore not safe for work texts.

    Output Format — respond in Markdown. Render EVERY section below as its own `## Heading` so each is clearly separated, and use bullet points (`-`) for all lists. Do NOT use numbered lists anywhere in the response.

    ## Input Query
    {query}

    ## Source Links Referenced for Analysis
    - every source link used for the analysis

    ## Leaked Corporate Artifacts
    - each artifact as a bullet (credentials, documents, source code, databases)

    ## Threat Actor / Broker Activity
    - each threat actor or broker activity as a bullet

    ## Business Impact Assessment
    - competitive or operational damage that could result from the exposure

    ## Key Insights
    - each insight on the corporate risk posture as its own bullet

    ## Next Steps
    - each IR action, legal consideration, or further query as its own bullet

    INPUT:
    """,
}


def generate_summary(llm, query, content, preset="threat_intel", custom_instructions=""):
    system_prompt = PRESET_PROMPTS.get(preset, PRESET_PROMPTS["threat_intel"])
    
    if not isinstance(content, str):
        try:
            content = json.dumps(content, indent=2)
        except Exception:
            pass
            
    invoke_vars = {"query": query, "content": content}
    if custom_instructions and custom_instructions.strip():
        # Append as a template placeholder filled by an invoke value, so literal
        # braces the user typed in Custom Instructions aren't misread as
        # prompt-template variables (same safe pattern as answer_followup).
        system_prompt = system_prompt.rstrip() + "\n\nAdditionally focus on: {custom_focus}"
        invoke_vars["custom_focus"] = custom_instructions.strip()
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke(invoke_vars)


# --- Conversational follow-up (v2.8) ---

# Persona per preset — the follow-up adopts the domain expertise of the selected
# preset, but answers conversationally instead of re-emitting the full report.
_FOLLOWUP_PERSONAS = {
    "threat_intel": "a Cybercrime Threat Intelligence Expert",
    "ransomware_malware": "a Malware and Ransomware Intelligence Expert",
    "personal_identity": "a Personal Threat Intelligence Expert",
    "corporate_espionage": "a Corporate Intelligence Expert",
}

_FOLLOWUP_SYSTEM = """
You are {persona}, answering follow-up questions about a dark web OSINT investigation that has already been completed.

Rules:
1. STRICT GROUNDING: Answer ONLY from the INVESTIGATION CONTEXT below and the conversation so far. If the answer is not present in the context, say so plainly — do not infer, extrapolate, or fabricate artifacts or claims.
2. Answer the specific question directly and conversationally. Do NOT reproduce the full structured report format; this is a chat.
3. When you reference an artifact or claim, point to the source link or section it came from in the context.
4. Be concise and analytical. Ignore not-safe-for-work text.
{extra_instructions}
INVESTIGATION CONTEXT:
{context}
"""


def build_followup_context(query, refined, sources, scraped, summary, enrichment_data=None, char_budget=12000):
    """Assemble the grounding context a follow-up is answered from:
    original + refined query, sources, the generated summary, and a
    char-budgeted slice of the raw scraped content (may be absent for
    investigations loaded from disk)."""
    parts = [f"ORIGINAL QUERY: {query}", f"REFINED QUERY: {refined}"]
    if sources:
        src_lines = "\n".join(
            f"- {s.get('title', 'Untitled')} ({s.get('link', '')})" for s in sources
        )
        parts.append("SOURCES:\n" + src_lines)
    if summary:
        parts.append("INVESTIGATION SUMMARY:\n" + str(summary))
    if enrichment_data:
        try:
            enrich_str = json.dumps(enrichment_data, indent=2)
            parts.append("OSINT ENRICHMENT DATA:\n" + enrich_str)
        except Exception:
            parts.append("OSINT ENRICHMENT DATA:\n" + str(enrichment_data))
    if scraped:
        if isinstance(scraped, str):
            raw = scraped
        else:
            try:
                raw = json.dumps(scraped, indent=2)
            except Exception:
                raw = str(scraped)
        if len(raw) > char_budget:
            raw = raw[:char_budget] + "\n\n[...truncated...]"
        parts.append("RAW SCRAPED CONTENT (may be truncated):\n" + raw)
    return "\n\n".join(parts)


def answer_followup(llm, question, context, history=None, preset="threat_intel", custom_instructions=""):
    """Answer a grounded follow-up question. `history` is a list of LangChain
    HumanMessage/AIMessage (already windowed by the caller). Streams if the llm
    has streaming callbacks attached; returns the full answer text."""
    persona = _FOLLOWUP_PERSONAS.get(preset, _FOLLOWUP_PERSONAS["threat_intel"])
    extra_instructions = ""
    if custom_instructions and custom_instructions.strip():
        extra_instructions = f"\nAlso keep in mind: {custom_instructions.strip()}\n"
    # Pass persona/context/extra as invoke VALUES (not baked into the template
    # string) so literal braces in scraped content or the summary are not
    # misread as prompt-template variables — the same safe pattern used by
    # generate_summary and suggest_pivots.
    prompt_template = ChatPromptTemplate(
        [
            ("system", _FOLLOWUP_SYSTEM),
            MessagesPlaceholder("history"),
            ("user", "{question}"),
        ]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({
        "persona": persona,
        "context": context,
        "extra_instructions": extra_instructions,
        "history": history or [],
        "question": question,
    })


def suggest_pivots(llm, query, content, preset="threat_intel", max_pivots=5):
    """Structured call: propose up to `max_pivots` short pivot search queries
    that would extend the investigation. Returns a list of strings (empty on
    any failure — pivots are a convenience, never block the pipeline)."""
    system_prompt = """
    You are a dark web OSINT investigator. Based on the completed investigation data below, propose concise follow-up SEARCH QUERIES that would pivot the investigation toward related leads — new artifacts, threat actor handles, marketplaces, forums, breach names, etc. that actually appear in or are strongly implied by the data.

    Rules:
    1. Each query must be 5 words or fewer, with no logical operators (AND, OR, etc.).
    2. Propose between 1 and {max_pivots} queries — only ones grounded in the data.
    3. Output ONLY a JSON array of strings, nothing else. Example: ["query one", "query two"]

    INVESTIGATION QUERY: {query}
    INVESTIGATION DATA:
    """.replace("{max_pivots}", str(max_pivots))

    if isinstance(content, str):
        raw_content = content
    else:
        try:
            raw_content = json.dumps(content, indent=2)
        except Exception:
            raw_content = str(content)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    # Use a fresh chain without streaming callbacks so the JSON isn't emitted to the UI.
    chain = prompt_template | llm | StrOutputParser()
    try:
        raw = chain.invoke({"query": query, "content": raw_content[:8000]})
    except Exception as e:
        logging.warning("Pivot suggestion call failed: %s", e)
        return []

    # Defensive parse: strip code fences, extract the first JSON array.
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text).rstrip("`").strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        pivots = json.loads(text)
    except Exception:
        return []
    if not isinstance(pivots, list):
        return []
    cleaned = []
    for p in pivots:
        if isinstance(p, str) and p.strip():
            cleaned.append(p.strip())
    return cleaned[:max_pivots]
