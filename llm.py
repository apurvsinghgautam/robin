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
    elif "ChatMistralAI" in class_name:
        from config import MISTRAL_API_KEY
        _require(MISTRAL_API_KEY, "MISTRAL_API_KEY", "Mistral")
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
    You are a Dark Web Search Query Expert. Your task is to refine the provided user query to get the best results from dark web search engines.

    Rules:
    1. Preserve the user's subject and intent exactly. Do NOT change the topic of the query: if the user asks about stock market data, keep it about stock market data; if about malware, keep it about malware.
    2. Add at most one dark-web discovery modifier relevant to the subject (e.g. "leak", "dump", "database", "breach", "forum", "dataset"), and only if it naturally fits the user's topic.
    3. Do NOT introduce unrelated topics like malware, ransomware, hacking, or CVEs unless the user's query is already about those topics.
    4. Preserve exact technical identifiers as-is: file hashes, onion addresses, usernames, CVE numbers, cryptocurrency addresses, email addresses.
    5. Avoid commercial or marketplace phrasing (e.g. "buy", "cheap", "price", "shop", "order").
    6. Don't use any logical operators (AND, OR, NOT, etc.).
    7. Keep the final refined query limited to 5 words or less.
    8. Output just the refined query and nothing else.

    INPUT:
    """
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


def _strip_leading_label(reply):
    """Drop a model's prose label so its numbers are not read as selections.

    Models answer "Top 5 results, ranked by relevance: 3, 9, 12". Taking the
    text after the last colon handles that, plus "Selected indices:\\n1, 4, 9"
    and JSON like {"indices": [2, 5, 9]}. Only applied when digits actually
    follow the colon, so "1, 2, 3: my picks" is left alone.
    """
    text = (reply or "").strip()
    head, sep, tail = text.rpartition(":")
    if sep and re.search(r"\d", tail):
        return tail
    return text


def filter_results(llm, query, results, limit=20):
    """Pick the results worth scraping, most relevant first.

    `limit` is the caller's real budget, not a fixed 20. The UI throws away
    anything past its "Max Pages to Scrape" slider, so asking the model for 20
    when the user set 5 made it rank fifteen results nobody would ever read and
    left a hidden third cap between two visible sliders.
    """
    if not results:
        return []

    limit = max(1, int(limit))

    system_prompt = """
    You are a Dark Web Search Result Analyst. You are given a user search query and a list of dark web search results (index, link, title).
    Your task is to select up to {limit} results that are most relevant to the user's search query topic.
    Rules:
    1. Select results based on how well they match the topic of the search query, not on how "cyber-crime-like" they look. If the query is about financial data or stock markets, prefer results about financial databases, data leaks or market data, NOT generic hacking or malware sites.
    2. Output ONLY at most the top {limit} indices (comma-separated list) that best match the input query, no more than {limit}.
    3. Do not repeat indices. Each index must appear at most once in your output.
    4. If none of the results are relevant to the query, output nothing at all. An empty answer is correct and expected when the search returned nothing on topic. Never pad the list with results you do not believe match.

    Search Query: {query}
    Search Results:
    """

    # Substitute the budget before the template is built, so ChatPromptTemplate
    # still sees only {query} as a variable.
    system_prompt = system_prompt.replace("{limit}", str(limit))

    final_str = _generate_final_string(results)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        print(
            f"Rate limit error: {e} \n Truncating to Web titles only with {TRUNCATED_TITLE_CHARS} characters"
        )
        final_str = _generate_final_string(results, truncate=True)
        try:
            result_indices = chain.invoke({"query": query, "results": final_str})
        except openai.RateLimitError:
            # A second 429 is the expected case inside one rate-limit window.
            # Raising from in here would surface as an unhandled error; an empty
            # selection is handled properly by the caller.
            logging.warning("Still rate limited after truncating. No results selected.")
            return []

    # Select top_k results using original (non-truncated) results.
    #
    # Strip a leading label before parsing. Models routinely answer "Top 7:
    # 3, 9, 12" or "Indices: 3, 9", and a bare \d+ scan reads the label's own
    # number as a selected index. Also require that a digit run is not glued to
    # a word or a minus sign, so "-4" and "v2" do not become selections.
    payload = _strip_leading_label(result_indices)
    parsed_indices = []
    for match in re.findall(r"(?<![\w-])(\d+)(?![\w])", payload):
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
        # No blind fallback. When the model selects nothing it is normally
        # because nothing in the raw list actually matches the query, and
        # forcing the top 20 through the scraper produced summaries written
        # from irrelevant pages (issue #146). Reporting zero results is the
        # honest answer; the caller stops the pipeline and says so.
        logging.info(
            "No relevant search results selected for query '%s' "
            "(model returned: %r). Returning zero results.",
            query,
            (result_indices or "").strip()[:200],
        )
        return []

    top_results = [results[i - 1] for i in parsed_indices[:limit]]

    return top_results


# How much of a title survives the rate-limit retry path. The old value of 30
# characters cut most titles mid-word, which left the filtering model guessing
# from fragments (issue #17). 120 sits in the range that issue asked for and
# still cuts the payload enough for a retry to get under the limit.
TRUNCATED_TITLE_CHARS = 120

# Characters kept when sanitizing a scraped title. Braces are deliberately
# excluded: dark web listings are full of them and they break LangChain prompt
# templates. Everything else here is ordinary punctuation that carries meaning,
# where the old alphanumeric-only scrub turned "ACME Corp: 400GB (leaked)" into
# "ACME Corp  400GB  leaked ".
# Punctuation worth keeping. Braces are excluded on purpose: dark web listings
# are full of them and they break LangChain prompt templates.
_TITLE_PUNCT = set("-.,:;/_()'\"&!?#@+ ")


def _sanitize_title(title: str) -> str:
    """Strip control characters and braces, keep letters in any script.

    An ASCII allowlist blanked every Cyrillic, CJK and Arabic title, and the
    caller's guard is an AND, so the result survived as a bare hostname with no
    title for the ranker to judge. isalnum is Unicode-aware.
    """
    cleaned = "".join(
        ch if (ch.isalnum() or ch in _TITLE_PUNCT) else " "
        for ch in (title or "")
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _generate_final_string(results, truncate=False):
    """
    Generate a formatted string from the search results for LLM processing.
    """

    if truncate:
        max_title_length = TRUNCATED_TITLE_CHARS
        # Do not use link at all
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        # Truncate link at .onion for display
        truncated_link = re.sub(r"(?<=\.onion).*", "", res["link"])
        title = _sanitize_title(res["title"])
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
    invoke_vars = {"query": query, "content": _flatten_scraped(content)}
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


def _flatten_scraped(scraped):
    """Render the scraper's {url: text} mapping as readable text.

    scrape_multiple returns a dict. Iterating a dict yields its KEYS, so three
    call sites were handing the model a bare list of onion hostnames and no page
    content whatsoever: follow-up chat could not answer questions about data it
    had scraped, pivots were generated from hostnames, and the summary got a raw
    Python dict repr. Tolerant of the str and list shapes that investigations
    loaded from disk can still carry.
    """
    if not scraped:
        return ""
    if isinstance(scraped, str):
        return scraped
    if isinstance(scraped, dict):
        return "\n\n".join(
            "SOURCE: {}\n{}".format(url, text)
            for url, text in scraped.items() if text
        )
    return "\n\n".join(str(x) for x in scraped)


def build_followup_context(query, refined, sources, scraped, summary, char_budget=12000):
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
    if scraped:
        raw = _flatten_scraped(scraped)
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

    raw_content = _flatten_scraped(content)
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
