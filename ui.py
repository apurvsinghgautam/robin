
import base64
import json
import re
import streamlit as st
from datetime import datetime
from pathlib import Path
from scrape import scrape_multiple
from search import get_search_results
import config as _robin_cfg
from llm_utils import BufferedStreamingHandler, get_model_choices, get_model_display_names
from llm import (
    get_llm, refine_query, filter_results, generate_summary, PRESET_PROMPTS,
    answer_followup, suggest_pivots, build_followup_context,
)
from langchain_core.messages import HumanMessage, AIMessage
from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENROUTER_API_KEY,
    OLLAMA_BASE_URL,
    LLAMA_CPP_BASE_URL,
)
from health import check_llm_health, check_search_engines, check_tor_proxy


def _render_pipeline_error(stage: str, err: Exception) -> None:
    message = str(err).strip() or err.__class__.__name__
    lower_msg = message.lower()
    hints = [
        "- Confirm the relevant API key is set in your `.env` or shell before launching Streamlit.",
        "- Keys copied from dashboards often include hidden spaces; re-copy if authentication keeps failing.",
        "- Restart the app after updating environment variables so the new values are picked up.",
    ]

    if any(token in lower_msg for token in ("anthropic", "x-api-key", "invalid api key", "authentication")):
        hints.insert(0, "- Claude/Anthropic models require a valid `ANTHROPIC_API_KEY`.")
    elif "openrouter" in lower_msg or "user not found" in lower_msg or "code: 401" in lower_msg:
        hints.insert(0, "- OpenRouter 401/User not found usually means the API key is invalid/expired or has leading/trailing characters.")
        hints.insert(1, "- Set `OPENROUTER_API_KEY` without extra spaces and verify the key is active in your OpenRouter account.")
        hints.insert(2, "- Keep `OPENROUTER_BASE_URL` as `https://openrouter.ai/api/v1` unless you intentionally use a custom gateway.")
    elif "openai" in lower_msg or "gpt" in lower_msg:
        hints.insert(0, "- OpenAI models require `OPENAI_API_KEY` with access to the chosen model.")
    elif any(t in lower_msg for t in ("context length", "context_length", "too many tokens",
                                      "maximum context", "reduce the length")):
        hints.insert(0, "- The investigation exceeded the model's context window. "
                        "Lower **Content per Page** or **Max Pages to Scrape** in the sidebar, "
                        "or pick a model with a larger window.")
        hints.insert(1, "- On Ollama, raise `OLLAMA_NUM_CTX` (see TROUBLESHOOTING.md).")
    elif "google" in lower_msg or "gemini" in lower_msg:
        hints.insert(0, "- Google Gemini models need `GOOGLE_API_KEY` or Application Default Credentials.")

    st.error(
        "❌ Failed to {}.\n\nError: {}\n\n{}".format(
            stage,
            message,
            "\n".join(hints),
        )
    )
    st.stop()


def _render_no_results(headline: str, hints: list) -> None:
    """Stop the pipeline and say plainly that nothing was found.

    Robin used to fall through to scraping and summarizing whatever links it
    happened to hold, which produced confident reports built from search engine
    navigation pages (issue #146). An empty result is a real answer.
    """
    st.warning("🔍 {}\n\n{}".format(headline, "\n".join(hints)))
    st.stop()


# --- Investigation persistence ---

INVESTIGATIONS_DIR = Path("investigations")


def save_investigation(query: str, refined_query: str, model: str, preset_label: str, sources: list, summary: str) -> str:
    """Save a completed investigation to disk. Returns the filename."""
    INVESTIGATIONS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"investigation_{timestamp}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "refined_query": refined_query,
        "model": model,
        "preset": preset_label,
        "sources": sources,
        "summary": summary,
    }
    (INVESTIGATIONS_DIR / fname).write_text(json.dumps(data, indent=2))
    return fname


def load_investigations() -> list:
    """Return list of saved investigations sorted newest-first."""
    if not INVESTIGATIONS_DIR.exists():
        return []
    files = sorted(INVESTIGATIONS_DIR.glob("investigation_*.json"), reverse=True)
    investigations = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            data["_filename"] = f.name
            investigations.append(data)
        except Exception:
            continue
    return investigations


# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query.replace(" ", "+"), max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int, content_chars: int):
    return scrape_multiple(filtered, max_workers=threads,
                           max_return_chars=content_chars)


# Streamlit page configuration
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown(
    """
    <style>
            .aStyle {
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
                padding-left: 0px;
                text-align: left;
            }
            .colHeight { max-height: 40vh; overflow-y: auto; text-align: center; }
            .pTitle { font-weight: bold; color: #FF4B4B; margin-bottom: 0.5em; }
    </style>""",
    unsafe_allow_html=True,
)


# Sidebar
st.sidebar.title("Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown(
    """Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)"""
)
st.sidebar.subheader("Settings")
def _env_is_set(value) -> bool:
    return bool(value and str(value).strip() and "your_" not in str(value))

# Seed session state from .env on first run (must happen before get_model_choices)
if "custom_api_url" not in st.session_state:
    st.session_state["custom_api_url"] = _robin_cfg.CUSTOM_API_BASE_URL or ""
if "custom_api_key" not in st.session_state:
    st.session_state["custom_api_key"] = _robin_cfg.CUSTOM_API_KEY or ""
if "custom_api_model" not in st.session_state:
    st.session_state["custom_api_model"] = _robin_cfg.CUSTOM_API_MODEL or ""

# Push current session values into config so llm_utils picks them up this rerun
_robin_cfg.CUSTOM_API_BASE_URL = st.session_state["custom_api_url"].strip() or None
_robin_cfg.CUSTOM_API_KEY = st.session_state["custom_api_key"].strip() or None
_robin_cfg.CUSTOM_API_MODEL = st.session_state["custom_api_model"].strip() or None

model_options = get_model_choices()
model_display_names = get_model_display_names(model_options)

# Preselect an inexpensive recent model. Match on the tier token rather than a
# model name: hardcoding one is what left "gpt4o" here long after that id was
# retired, so the search always missed and silently fell through to index 0.
# The registry already orders each provider newest-first, so the first token
# match is the newest cheap model the user can actually reach.
_CHEAP_TIER_TOKENS = ("nano", "mini", "flash-lite", "flash", "lite", "haiku", "small")


def _has_tier_token(name: str, token: str) -> bool:
    """Match a tier token as a whole segment, not a bare substring.

    "mini" is a substring of "gemini", so a plain `in` test made every Gemini
    model read as a mini model and the preselection landed wherever the list
    happened to start.
    """
    return re.search(r"(?:^|[-_. /:])" + re.escape(token) + r"(?:$|[-_. /:])",
                     name.lower()) is not None


def _default_model_index(options) -> int:
    for token in _CHEAP_TIER_TOKENS:
        for idx, name in enumerate(options):
            if _has_tier_token(name, token):
                return idx
    return 0


default_model_index = _default_model_index(model_options) if model_options else 0

if not model_options:
    st.sidebar.error(
        "⛔ **No LLM models available.**\n\n"
        "No API keys or local providers are configured. "
        "Set at least one in your `.env` file and restart Robin.\n\n"
        "See **Provider Configuration** below for details."
    )
    st.stop()

model = st.sidebar.selectbox(
    "Select LLM Model",
    model_options,
    format_func=lambda m: model_display_names.get(m, m),
    index=default_model_index,
    key="model_select",
)
if any(model_display_names.get(name, "").startswith("[ollama]") for name in model_options):
    st.sidebar.caption("Locally detected Ollama models are automatically added to this list.")

with st.sidebar.expander("🔌 Custom API Provider"):
    st.text_input(
        "Base URL",
        key="custom_api_url",
        placeholder="https://api.groq.com/openai/v1",
        help="Base URL for any OpenAI-compatible API (Groq, Mistral, LM Studio, etc.)",
    )
    st.text_input(
        "API Key",
        key="custom_api_key",
        type="password",
        help="API key for the custom provider (leave blank if not required)",
    )
    st.text_input(
        "Model Name",
        key="custom_api_model",
        placeholder="llama-3.3-70b-versatile",
        help="Model to use. Required if the provider doesn't expose /v1/models for auto-discovery.",
    )
threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")
max_results = st.sidebar.slider(
    "Max Results to Filter", 10, 100, 50, key="max_results_slider",
    help="Cap the number of raw search results passed to the LLM filter step.",
)
max_scrape = st.sidebar.slider(
    "Max Pages to Scrape", 3, 20, 10, key="max_scrape_slider",
    help="Cap the number of filtered results that get scraped for content.",
)
content_chars = st.sidebar.slider(
    "Content per Page (characters)", 1000, 20000, 8000, step=1000,
    key="content_chars_slider",
    help="How much of each scraped page the model reads. Higher means richer "
         "reports and more tokens per investigation. Raising this does not slow "
         "down the Tor scrape.",
)
st.sidebar.caption(
    "~{:,} characters (~{:,} tokens) sent to the model per investigation.".format(
        content_chars * max_scrape, (content_chars * max_scrape) // 4
    )
)

st.sidebar.divider()
st.sidebar.subheader("Provider Configuration")
_providers = [
    ("OpenAI",      OPENAI_API_KEY,     True),
    ("Anthropic",   ANTHROPIC_API_KEY,  True),
    ("Google",      GOOGLE_API_KEY,     True),
    ("OpenRouter",  OPENROUTER_API_KEY, True),
    ("Ollama",      OLLAMA_BASE_URL,    False),
    ("llama.cpp",   LLAMA_CPP_BASE_URL, False),
]
for name, value, is_cloud in _providers:
    if _env_is_set(value):
        st.sidebar.markdown(f"&ensp;✅ **{name}** — configured")
    elif is_cloud:
        st.sidebar.markdown(f"&ensp;⚠️ **{name}** — API key not set")
    else:
        st.sidebar.markdown(f"&ensp;🔵 **{name}** — not configured *(optional)*")

with st.sidebar.expander("⚙️ Prompt Settings"):
    preset_options = {
        "🔍 Dark Web Threat Intel": "threat_intel",
        "🦠 Ransomware / Malware Focus": "ransomware_malware",
        "👤 Personal / Identity Investigation": "personal_identity",
        "🏢 Corporate Espionage / Data Leaks": "corporate_espionage",
    }
    preset_placeholders = {
        "threat_intel": "e.g. Pay extra attention to cryptocurrency wallet addresses and exchange names.",
        "ransomware_malware": "e.g. Highlight any references to double-extortion tactics or known ransomware-as-a-service affiliates.",
        "personal_identity": "e.g. Flag any passport or government ID numbers and note which country they appear to be from.",
        "corporate_espionage": "e.g. Prioritize any mentions of source code repositories, API keys, or internal Slack/email dumps.",
    }
    selected_preset_label = st.selectbox(
        "Research Domain",
        list(preset_options.keys()),
        key="preset_select",
    )
    selected_preset = preset_options[selected_preset_label]
    st.text_area(
        "System Prompt",
        value=PRESET_PROMPTS[selected_preset].strip(),
        height=200,
        disabled=True,
        key="system_prompt_display",
    )
    custom_instructions = st.text_area(
        "Custom Instructions (optional)",
        placeholder=preset_placeholders[selected_preset],
        height=100,
        key="custom_instructions",
    )

# --- Health Checks ---
st.sidebar.divider()
st.sidebar.subheader("Health Checks")

# LLM Health Check
if st.sidebar.button("🔌 Check LLM Connection", use_container_width=True):
    with st.sidebar:
        with st.spinner(f"Testing {model}..."):
            result = check_llm_health(model)
        if result["status"] == "up":
            st.sidebar.success(
                f"✅ **{result['provider']}** — Connected ({result['latency_ms']}ms)"
            )
        else:
            st.sidebar.error(
                f"❌ **{result['provider']}** — Failed\n\n{result['error']}"
            )

# Search Engine Health Check
if st.sidebar.button("🔍 Check Search Engines", use_container_width=True):
    with st.sidebar:
        with st.spinner("Checking Tor proxy..."):
            tor_result = check_tor_proxy()
        if tor_result["status"] == "down":
            st.sidebar.error(
                f"❌ **Tor Proxy** — Not reachable\n\n{tor_result['error']}\n\n"
                "Ensure Tor is running: `sudo systemctl start tor`"
            )
        else:
            st.sidebar.success(
                f"✅ **Tor Proxy** — Connected ({tor_result['latency_ms']}ms)"
            )
            with st.spinner("Pinging 16 search engines via Tor..."):
                engine_results = check_search_engines()
            up_count = sum(1 for r in engine_results if r["status"] == "up")
            total = len(engine_results)
            if up_count == total:
                st.sidebar.success(f"✅ **All {total} engines reachable**")
            elif up_count > 0:
                st.sidebar.warning(f"⚠️ **{up_count}/{total} engines reachable**")
            else:
                st.sidebar.error(f"❌ **0/{total} engines reachable**")

            for r in engine_results:
                if r["status"] == "up":
                    st.sidebar.markdown(
                        f"&ensp;🟢 **{r['name']}** — {r['latency_ms']}ms"
                    )
                else:
                    st.sidebar.markdown(
                        f"&ensp;🔴 **{r['name']}** — {r['error']}"
                    )

# --- Past Investigations ---
st.sidebar.divider()
st.sidebar.subheader("📂 Past Investigations")
saved_investigations = load_investigations()
if saved_investigations:
    inv_labels = [
        f"{inv['_filename'].replace('investigation_','').replace('.json','')} — {inv['query'][:40]}"
        for inv in saved_investigations
    ]
    selected_inv_label = st.sidebar.selectbox(
        "Load investigation", ["(none)"] + inv_labels, key="inv_select"
    )
    if selected_inv_label != "(none)":
        selected_inv_idx = inv_labels.index(selected_inv_label)
        if st.sidebar.button("📂 Load", use_container_width=True, key="load_inv_btn"):
            _saved = saved_investigations[selected_inv_idx]
            # Saved "preset" is the display label; map back to the preset key for follow-ups.
            _saved_preset = _saved.get("preset", "threat_intel")
            if _saved_preset in preset_options:
                _preset_key = preset_options[_saved_preset]
            elif _saved_preset in preset_options.values():
                _preset_key = _saved_preset
            else:
                _preset_key = "threat_intel"
            st.session_state["active_investigation"] = {
                "query": _saved.get("query", ""),
                "refined": _saved.get("refined_query", ""),
                "model": _saved.get("model", ""),
                "preset": _preset_key,
                "preset_label": _saved.get("preset", ""),
                "sources": _saved.get("sources", []),
                "scraped": None,  # raw scrape isn't persisted to disk
                "summary": _saved.get("summary", ""),
                "results_count": len(_saved.get("sources", [])),
                "timestamp": _saved.get("timestamp", ""),
            }
            st.session_state["chat_history"] = []
            st.session_state["pivot_suggestions"] = []
            st.rerun()
else:
    st.sidebar.caption("No saved investigations yet.")


# Main UI - logo and input
_, logo_col, _ = st.columns(3)
with logo_col:
    st.image(".github/assets/robin_logo.png", width=200)

# Display text box and button
with st.form("search_form", clear_on_submit=True):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "Enter Dark Web Search Query",
        placeholder="Enter Dark Web Search Query",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("Run")

# (Completed and loaded investigations are rendered by the unified active-investigation
#  block below, so they survive chat reruns.)

# Status + result section placeholders
status_slot = st.empty()
_stat_cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in _stat_cols]
notes_placeholder = st.empty()
sources_placeholder = st.empty()
findings_placeholder = st.empty()


# --- Active investigation + follow-up chat helpers (v2.8) ---

def _render_investigation_body(inv):
    """Render Notes / Sources / Findings / Download for a stored investigation."""
    with st.expander("📋 Notes", expanded=False):
        st.markdown(f"**Refined Query:** `{inv.get('refined', '')}`")
        st.markdown(
            f"**Model:** `{inv.get('model', '')}` &nbsp;&nbsp; "
            f"**Domain:** {inv.get('preset_label') or inv.get('preset', '')}"
        )
        _counts = f"**Sources:** {len(inv.get('sources', []))}"
        if inv.get("scraped"):
            _counts += f" &nbsp;&nbsp; **Scraped:** {len(inv['scraped'])}"
        st.markdown(_counts)
    sources = inv.get("sources", [])
    with st.expander(f"🔗 Sources ({len(sources)} results)", expanded=False):
        for i, item in enumerate(sources, 1):
            st.markdown(f"{i}. [{item.get('title', 'Untitled')}]({item.get('link', '')})")
    st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
    summary = inv.get("summary", "") or ""
    st.markdown(summary)
    if summary:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        b64 = base64.b64encode(summary.encode()).decode()
        href = (
            f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" '
            f'download="summary_{now}.md">Download</a></div>'
        )
        st.markdown(href, unsafe_allow_html=True)


def _followup_history_messages(chat_history, max_turns=5):
    """Convert the last `max_turns` Q&A turns into LangChain messages for the model."""
    recent = chat_history[-(max_turns * 2):] if chat_history else []
    msgs = []
    for turn in recent:
        if turn.get("role") == "user":
            msgs.append(HumanMessage(content=turn.get("content", "")))
        else:
            msgs.append(AIMessage(content=turn.get("content", "")))
    return msgs


def _render_chat_panel(inv):
    """Suggested pivots, chat history, clear control, and the follow-up input."""
    st.divider()
    st.subheader(":red[💬 Follow-up Chat]", anchor=None, divider="gray")

    # Suggested pivots — one click launches a new foreground investigation.
    pivots = st.session_state.get("pivot_suggestions", [])
    if pivots:
        st.caption("Suggested pivots — click to run as a new investigation:")
        pivot_cols = st.columns(len(pivots))
        for i, (col, pq) in enumerate(zip(pivot_cols, pivots)):
            if col.button(f"🔎 {pq}", key=f"pivot_{i}", use_container_width=True):
                st.session_state["pivot_query"] = pq
                st.rerun()

    # Existing conversation.
    for turn in st.session_state.get("chat_history", []):
        with st.chat_message(turn.get("role", "assistant")):
            st.markdown(turn.get("content", ""))

    if st.session_state.get("chat_history"):
        if st.button("🧹 Clear chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()

    # New follow-up — grounded in this investigation's context.
    followup = st.chat_input("Ask a follow-up about this investigation")
    if followup:
        with st.chat_message("user"):
            st.markdown(followup)
        # Budget the follow-up against the same amount of evidence the summary
        # saw. A fixed 12,000 would answer chat questions from a fraction of a
        # high-budget investigation while the report used all of it.
        _inv_budget = inv.get("content_chars") and inv.get("max_scrape")
        context = build_followup_context(
            inv.get("query", ""), inv.get("refined", ""),
            inv.get("sources", []), inv.get("scraped"), inv.get("summary", ""),
            char_budget=(inv["content_chars"] * inv["max_scrape"]) if _inv_budget else 12000,
        )
        history = _followup_history_messages(st.session_state.get("chat_history", []))
        with st.chat_message("assistant"):
            answer_slot = st.empty()
            acc = {"text": ""}

            def _emit(chunk: str):
                acc["text"] += chunk
                answer_slot.markdown(acc["text"])

            try:
                f_llm = get_llm(inv.get("model"))
                f_llm.callbacks = [BufferedStreamingHandler(ui_callback=_emit)]
                answer = answer_followup(
                    f_llm, followup, context, history=history,
                    preset=inv.get("preset", "threat_intel"),
                )
                # #137 pattern: reasoning models stream nothing — fall back to the return value.
                if not acc["text"].strip() and answer:
                    acc["text"] = answer
                    answer_slot.markdown(answer)
            except Exception as e:
                acc["text"] = f"⚠️ Failed to answer follow-up: {e}"
                answer_slot.markdown(acc["text"])

        st.session_state.setdefault("chat_history", [])
        st.session_state["chat_history"].append({"role": "user", "content": followup})
        st.session_state["chat_history"].append({"role": "assistant", "content": acc["text"]})


# A run is triggered by a submitted query OR a one-click pivot from the chat panel.
_pivot_query = st.session_state.pop("pivot_query", None)
_active_query = _pivot_query or query
_do_run = bool(_active_query) and (run_button or _pivot_query is not None)

# Process the query
if _do_run:
    query = _active_query
    # Clear any prior investigation, chat, and pipeline state
    st.session_state.pop("active_investigation", None)
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary",
              "chat_history", "pivot_suggestions"]:
        st.session_state.pop(k, None)

    # Stage 1 - Load LLM
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            try:
                llm = get_llm(model)
            except Exception as e:
                _render_pipeline_error("load the selected LLM", e)

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            try:
                st.session_state.refined = refine_query(llm, query)
            except Exception as e:
                _render_pipeline_error("refine the query", e)
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            try:
                st.session_state.results = cached_search_results(
                    st.session_state.refined, threads
                )
            except Exception as e:
                _render_pipeline_error("search the dark web", e)
    if not st.session_state.results:
        _render_no_results(
            "No dark web results came back for this query.",
            [
                "- Try broader or differently worded search terms.",
                "- Run **Check Search Engines** in the sidebar; onion engines have irregular uptime.",
                "- Confirm Tor is running and reachable on `socks5h://127.0.0.1:9050`.",
            ],
        )

    # Cap results before LLM filter step
    if len(st.session_state.results) > max_results:
        st.session_state.results = st.session_state.results[:max_results]
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            try:
                st.session_state.filtered = filter_results(
                    llm, st.session_state.refined, st.session_state.results,
                    limit=max_scrape,
                )
            except Exception as e:
                _render_pipeline_error("filter the search results", e)
    if not st.session_state.filtered:
        _render_no_results(
            "Found {} raw links, but none of them matched this query.".format(
                len(st.session_state.results)
            ),
            [
                "- The engines that responded returned nothing relevant to these terms.",
                "- Try broader terms, or a different phrasing of the same question.",
                "- Robin stops here on purpose rather than summarizing unrelated pages.",
            ],
        )

    # Cap filtered results before scraping
    if len(st.session_state.filtered) > max_scrape:
        st.session_state.filtered = st.session_state.filtered[:max_scrape]
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            try:
                st.session_state.scraped = cached_scrape_multiple(
                    st.session_state.filtered, threads, content_chars
                )
            except Exception as e:
                _render_pipeline_error("scrape the selected pages", e)

    # Stage 6 - Summarize (streaming)
    st.session_state.streamed_summary = ""

    with findings_placeholder.container():
        st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
        summary_slot = st.empty()

    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            try:
                summary_text = generate_summary(
                    llm, query, st.session_state.scraped,
                    preset=selected_preset, custom_instructions=custom_instructions,
                )
            except Exception as e:
                _render_pipeline_error("generate the investigation summary", e)

    # Reasoning models (OpenAI o1, DeepSeek R1, etc.) stream their chain-of-thought as
    # reasoning_content, so on_llm_new_token never fires with answer tokens and the
    # streamed buffer stays empty. generate_summary() still returns the full text via
    # invoke, so fall back to it whenever nothing was streamed — otherwise the Findings
    # panel, the saved investigation, and the download are all blank for reasoning models.
    if not st.session_state.streamed_summary.strip() and summary_text:
        st.session_state.streamed_summary = summary_text
        summary_slot.markdown(summary_text)

    # Save investigation
    _fname = save_investigation(
        query=query,
        refined_query=st.session_state.refined,
        model=model,
        preset_label=selected_preset_label,
        sources=st.session_state.filtered,
        summary=st.session_state.streamed_summary,
    )

    # Render organized sections
    with notes_placeholder.container():
        with st.expander("📋 Notes", expanded=False):
            st.markdown(f"**Refined Query:** `{st.session_state.refined}`")
            st.markdown(f"**Model:** `{model}` &nbsp;&nbsp; **Domain:** {selected_preset_label}")
            st.markdown(
                f"**Results found:** {len(st.session_state.results)} &nbsp;&nbsp; "
                f"**Filtered to:** {len(st.session_state.filtered)} &nbsp;&nbsp; "
                f"**Scraped:** {len(st.session_state.scraped)}"
            )

    with sources_placeholder.container():
        with st.expander(f"🔗 Sources ({len(st.session_state.filtered)} results)", expanded=False):
            for i, item in enumerate(st.session_state.filtered, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                st.markdown(f"{i}. [{title}]({link})")

    with findings_placeholder.container():
        st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
        st.markdown(st.session_state.streamed_summary)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)

    status_slot.success(f"✔️ Pipeline completed successfully! Investigation saved as `{_fname}`")

    # Persist as the active investigation so it survives chat reruns.
    st.session_state["active_investigation"] = {
        "query": query,
        "refined": st.session_state.refined,
        "model": model,
        "preset": selected_preset,
        "preset_label": selected_preset_label,
        "sources": st.session_state.filtered,
        "scraped": st.session_state.scraped,
        "summary": st.session_state.streamed_summary,
        "results_count": len(st.session_state.results),
        "content_chars": content_chars,
        "max_scrape": max_scrape,
    }
    st.session_state["chat_history"] = []

    # Suggested pivots — structured call on a fresh LLM with no UI callback
    # attached, so the JSON is never emitted to the Streamlit view. Never blocks
    # the pipeline.
    with st.spinner("💡 Suggesting pivots..."):
        try:
            st.session_state["pivot_suggestions"] = suggest_pivots(
                get_llm(model), query, st.session_state.scraped, preset=selected_preset,
            )
        except Exception:
            st.session_state["pivot_suggestions"] = []

    _render_chat_panel(st.session_state["active_investigation"])

# Returning visit (no run this pass, e.g. after a chat submit or a loaded
# investigation): render the active investigation and its chat panel.
elif st.session_state.get("active_investigation"):
    _inv = st.session_state["active_investigation"]
    _ts = _inv.get("timestamp")
    st.info(f"📂 **{_inv.get('query', '')}**" + (f" — {_ts[:16]}" if _ts else ""))
    _render_investigation_body(_inv)
    _render_chat_panel(_inv)
