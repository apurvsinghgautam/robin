import re
import json
import openai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from llm_utils import _common_llm_params, resolve_model_config, get_model_choices
from config import RobinConfig
from scrape import fence_overhead, fence_untrusted
# Prompt text lives in prompts.py, so the MCP server serves the exact words
# this module sends.
from prompts import (
    FILTER_SYSTEM_PROMPT,
    FOLLOWUP_PERSONAS,
    FOLLOWUP_SYSTEM,
    PIVOTS_SYSTEM_PROMPT,
    PRESET_PROMPTS,
    REFINE_SYSTEM_PROMPT,
)
from typing import Optional
import logging

import warnings

warnings.filterwarnings("ignore")


def get_llm(model_choice, cfg: Optional[RobinConfig] = None):
    """Build a chat client for `model_choice`.

    `cfg` is the configuration to build against; omitted, the environment.
    """
    cfg = cfg if cfg is not None else RobinConfig.from_env()

    model_cfg = resolve_model_config(model_choice, cfg)

    if model_cfg is None:
        supported_models = get_model_choices(cfg)
        raise ValueError(
            f"Unsupported LLM model: '{model_choice}'. "
            f"Supported models (case-insensitive match) are: {', '.join(supported_models)}"
        )

    llm_class = model_cfg["class"]
    model_specific_params = model_cfg["constructor_params"]

    # Model-specific parameters win, e.g. a local endpoint's streaming=False.
    all_params = {**_common_llm_params, **model_specific_params}

    _ensure_credentials(model_choice, llm_class, model_specific_params, cfg)

    llm_instance = llm_class(**all_params)

    return llm_instance


def _ensure_credentials(model_choice: str, llm_class, model_params: dict,
                        cfg: RobinConfig) -> None:
    """Raise a clear error if the user selects a hosted model without a key."""
    custom_api_base_url = cfg.custom_api_base_url

    def _require(key_value, env_var, provider_name):
        if key_value:
            return
        raise ValueError(
            f"{provider_name} model '{model_choice}' selected but `{env_var}` is not set.\n"
            "Add it to your .env file or export it before running the app."
        )

    class_name = getattr(llm_class, "__name__", str(llm_class))

    if "ChatAnthropic" in class_name:
        _require(cfg.anthropic_api_key, "ANTHROPIC_API_KEY", "Anthropic")
    elif "ChatMistralAI" in class_name:
        _require(cfg.mistral_api_key, "MISTRAL_API_KEY", "Mistral")
    elif "ChatGoogleGenerativeAI" in class_name:
        _require(cfg.google_api_key, "GOOGLE_API_KEY", "Google Gemini")
    elif "ChatOpenAI" in class_name:
        base_url = (model_params or {}).get("base_url", "").lower()
        if "openrouter" in base_url:
            _require(cfg.openrouter_api_key, "OPENROUTER_API_KEY", "OpenRouter")
        elif base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
            pass  # A local model needs no API key.
        elif custom_api_base_url and base_url and custom_api_base_url.lower().rstrip("/") in base_url:
            pass  # A custom provider's API key is optional.
        else:
            _require(cfg.openai_api_key, "OPENAI_API_KEY", "OpenAI")


def refine_query(llm, user_input):
    system_prompt = REFINE_SYSTEM_PROMPT
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{query}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    return chain.invoke({"query": user_input})


# A range lives on one line, so in "- 3\n- 9" the bullet hyphen is not read
# as a range dash.
_RANGE_RE = re.compile(r"(?<![\w-])(\d+)[ \t]*[-\u2013][ \t]*(\d+)(?![\w])")
_INDEX_RE = re.compile(r"(?<![\w-])(\d+)(?![\w])")
# Markdown list markers. The ordinal in "1. Index 3" numbers the list, not the
# result, so it must not reach the index scan.
_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*(?:\d+[.)]|[-*\u2022])[ \t]+")


def _iter_selected_indices(payload, max_span=100):
    """Yield the indices a model selected, expanding "10-12" style ranges."""
    payload = _LIST_MARKER_RE.sub("", payload or "")
    consumed = []
    for match in _RANGE_RE.finditer(payload):
        start, end = int(match.group(1)), int(match.group(2))
        if 0 < end - start < max_span:
            consumed.append((match.span(), list(range(start, end + 1))))

    out, covered = [], set()
    for (span, values) in consumed:
        covered.update(range(*span))
    expanded = {span[0]: values for span, values in consumed}
    for match in _INDEX_RE.finditer(payload):
        if match.start() in covered and match.start() not in expanded:
            continue
        if match.start() in expanded:
            out.extend(expanded[match.start()])
        else:
            out.append(int(match.group(1)))
    return out


# A second labelled line the model appended after its selection, e.g.
# "Reasoning: ..." or "Note: ...". Its prose carries years and URLs that the
# index scanner would otherwise read as selections.
_TRAILING_LABEL_RE = re.compile(r"\n\s*[A-Za-z][^\n:]{0,40}:")


def _strip_leading_label(reply):
    """Drop a model's prose label so its numbers are not read as selections."""
    text = (reply or "").strip()
    head, sep, tail = text.partition(":")
    if not (sep and re.search(r"\d", tail)):
        return text
    cut = _TRAILING_LABEL_RE.search(tail)
    return tail[:cut.start()] if cut else tail


def filter_results(llm, query, results, limit=20):
    """Pick up to `limit` results worth scraping, most relevant first.

    `limit` is the caller's scrape budget, so the model ranks only what is read.
    """
    return filter_results_detailed(llm, query, results, limit=limit)[0]


def filter_results_detailed(llm, query, results, limit=20):
    """`filter_results`, plus the model's raw reply: (selected, reply)."""
    if not results:
        return [], None

    limit = max(1, int(limit))

    # Substitute the budget before the template is built, so ChatPromptTemplate
    # still sees only {query} as a variable.
    system_prompt = FILTER_SYSTEM_PROMPT.replace("{limit}", str(limit))

    final_str = _fenced_result_list(results)

    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{results}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        result_indices = chain.invoke({"query": query, "results": final_str})
    except openai.RateLimitError as e:
        logging.warning(
            "Rate limited (%s). Truncating to web titles only with %d characters.",
            e, TRUNCATED_TITLE_CHARS,
        )
        # A second 429 propagates: a rate limit is a failed filter, not a
        # judgment that nothing was relevant.
        final_str = _fenced_result_list(results, truncate=True)
        result_indices = chain.invoke({"query": query, "results": final_str})

    # Strip a leading label before parsing: in "Top 7: 3, 9, 12" the 7 belongs
    # to the label and is not a selected index.
    payload = _strip_leading_label(result_indices)
    parsed_indices = []
    # The span grows with the list: with 101 results "1-101" is a valid answer.
    for token in _iter_selected_indices(payload, max_span=max(100, len(results))):
        if 1 <= token <= len(results):
            parsed_indices.append(token)

    # Remove duplicates while preserving order.
    seen = set()
    parsed_indices = [
        i for i in parsed_indices if not (i in seen or seen.add(i))
    ]

    if not parsed_indices:
        # No blind fallback. An empty selection normally means nothing matches
        # the query; the caller stops and says so rather than summarizing
        # unrelated pages.
        logging.info(
            "No relevant search results selected for query '%s' "
            "(model returned: %r). Returning zero results.",
            query,
            (result_indices or "").strip()[:200],
        )
        return [], result_indices

    top_results = [results[i - 1] for i in parsed_indices[:limit]]

    return top_results, result_indices


# How much of a title survives the rate-limit retry path: long enough to judge
# a title by, short enough to bring the payload under the limit.
TRUNCATED_TITLE_CHARS = 120

# Characters kept when sanitizing a scraped title. Braces are deliberately
# excluded: dark web listings are full of them and they break LangChain prompt
# templates.
_TITLE_PUNCT = set("-.,:;/_()'\"&!?#@+ ")


def _sanitize_title(title: str) -> str:
    """Strip control characters and braces, keep letters in any script.

    isalnum is Unicode-aware, so Cyrillic, CJK and Arabic titles survive.
    """
    cleaned = "".join(
        ch if (ch.isalnum() or ch in _TITLE_PUNCT) else " "
        for ch in (title or "")
    )
    return re.sub(r"\s+", " ", cleaned).strip()


# The fence label for anything an engine wrote: titles are anchor text on a page
# Robin does not control, so they are page data like any scraped body.
SEARCH_RESULTS_SOURCE = "dark web search engine results"


def _fenced_result_list(results, truncate=False):
    """The numbered result list the filter reads, inside one complete fence.

    Titles are engine-written, so they reach the model only as data. Trimming
    happens in `_generate_final_string`; the fence goes on last and is never cut.
    """
    return fence_untrusted(_generate_final_string(results, truncate=truncate),
                           SEARCH_RESULTS_SOURCE)


def _generate_final_string(results, truncate=False):
    """The search results as numbered `N. link - title` lines for the model."""

    if truncate:
        max_title_length = TRUNCATED_TITLE_CHARS
        # Do not use the link at all.
        max_link_length = 0

    final_str = []
    for i, res in enumerate(results):
        # Cut the link after .onion for display.
        truncated_link = re.sub(r"(?<=\.onion).*", "", res["link"])
        title = _sanitize_title(res["title"])
        if truncated_link == "" and title == "":
            continue

        if truncate:
            title = (
                title[:max_title_length] + "..."
                if len(title) > max_title_length
                else title
            )
            truncated_link = (
                truncated_link[:max_link_length] + "..."
                if len(truncated_link) > max_link_length
                else truncated_link
            )

        final_str.append(f"{i+1}. {truncated_link} - {title}")

    return "\n".join(s for s in final_str)


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


# --- Conversational follow-up ---

_PAGE_SEPARATOR = "\n\n"
# The source label for pages that carry no URL: a str or list `scraped`.
_UNKNOWN_SOURCE = "unknown source"


def _scraped_pages(scraped):
    """(source, text) for every non-empty page, whatever shape `scraped` has.

    A dict is scrape_multiple's {url: text}; a str or list has no known source.
    """
    if not scraped:
        return []
    if isinstance(scraped, str):
        return [(_UNKNOWN_SOURCE, scraped)]
    if isinstance(scraped, dict):
        return [(str(url), str(text)) for url, text in scraped.items() if text]
    return [(_UNKNOWN_SOURCE, str(item)) for item in scraped if item]


def _omission_note(count):
    return "[{} more scraped page{} omitted to fit the context budget]".format(
        count, "" if count == 1 else "s")


def _flatten_scraped(scraped, char_budget=None):
    """Render scraped pages as model input, each page inside its own fence."""
    pages = _scraped_pages(scraped)
    if not pages:
        return ""
    if char_budget is None:
        return _PAGE_SEPARATOR.join(fence_untrusted(text, url) for url, text in pages)

    budget = max(0, int(char_budget))
    kept = list(pages)
    while kept:
        overhead = (sum(fence_overhead(url) for url, _ in kept)
                    + len(_PAGE_SEPARATOR) * (len(kept) - 1))
        dropped = len(pages) - len(kept)
        note = (_PAGE_SEPARATOR + _omission_note(dropped)) if dropped else ""
        if overhead + len(note) <= budget:
            break
        kept.pop()
    if not kept:
        note = _omission_note(len(pages))
        return note if len(note) <= budget else ""

    # Water-fill the room left after the delimiters: each page, shortest
    # first, takes what it needs up to an equal share of what remains.
    room = budget - overhead - len(note)
    needs = [len(fence_untrusted(text, url)) - fence_overhead(url) for url, text in kept]
    allowance = [0] * len(kept)
    for position, index in enumerate(sorted(range(len(kept)), key=needs.__getitem__)):
        share = room // (len(kept) - position)
        allowance[index] = min(needs[index], share)
        room -= allowance[index]

    blocks = [
        fence_untrusted(text, url, max_chars=fence_overhead(url) + allowance[index])
        for index, (url, text) in enumerate(kept)
    ]
    return _PAGE_SEPARATOR.join(blocks) + note


def build_followup_context(query, refined, sources, scraped, summary, char_budget=12000):
    """Assemble the grounding context a follow-up is answered from.

    Original and refined query, sources, summary, and a char-budgeted slice of
    the scraped pages (absent for investigations loaded from disk)."""
    parts = [f"ORIGINAL QUERY: {query}", f"REFINED QUERY: {refined}"]
    if sources:
        src_lines = "\n".join(
            f"- {s.get('title', 'Untitled')} ({s.get('link', '')})" for s in sources
        )
        # Titles are engine-written: fenced like the pages they point at.
        parts.append("SOURCES:\n" + fence_untrusted(src_lines, SEARCH_RESULTS_SOURCE))
    if summary:
        parts.append("INVESTIGATION SUMMARY:\n" + str(summary))
    if scraped:
        # The budget goes to the flattener rather than a slice afterwards, so
        # every page's fence reaches the model with its closing line.
        raw = _flatten_scraped(scraped, char_budget=char_budget)
        parts.append("RAW SCRAPED CONTENT (may be truncated):\n" + raw)
    return "\n\n".join(parts)


def answer_followup(llm, question, context, history=None, preset="threat_intel", custom_instructions=""):
    """Answer a grounded follow-up question. `history` is a list of LangChain
    HumanMessage/AIMessage (already windowed by the caller). Streams if the llm
    has streaming callbacks attached; returns the full answer text."""
    persona = FOLLOWUP_PERSONAS.get(preset, FOLLOWUP_PERSONAS["threat_intel"])
    extra_instructions = ""
    if custom_instructions and custom_instructions.strip():
        extra_instructions = f"\nAlso keep in mind: {custom_instructions.strip()}\n"
    # Pass persona/context/extra as invoke VALUES (not baked into the template
    # string) so literal braces in scraped content or the summary are not
    # misread as prompt-template variables.
    prompt_template = ChatPromptTemplate(
        [
            ("system", FOLLOWUP_SYSTEM),
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


# How much scraped text the pivot suggestions read.
PIVOTS_CONTENT_CHARS = 8000


def suggest_pivots(llm, query, content, preset="threat_intel", max_pivots=5):
    """Structured call: propose up to `max_pivots` short pivot search queries
    that would extend the investigation. Returns a list of strings (empty on
    any failure — pivots are a convenience, never block the pipeline)."""
    system_prompt = PIVOTS_SYSTEM_PROMPT.replace("{max_pivots}", str(max_pivots))

    # The budget is spent inside the flattener, not sliced off afterwards,
    # so the last page's fence keeps its closing line.
    raw_content = _flatten_scraped(content, char_budget=PIVOTS_CONTENT_CHARS)
    prompt_template = ChatPromptTemplate(
        [("system", system_prompt), ("user", "{content}")]
    )
    chain = prompt_template | llm | StrOutputParser()
    try:
        raw = chain.invoke({"query": query, "content": raw_content})
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
