
import base64
import streamlit as st
import model_registry
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime
from scrape import scrape_multiple
from search import engines_unreachable, get_search_results_detailed
from llm_utils import (
    BufferedStreamingHandler,
    default_model,
    get_model_choices,
    get_model_display_names,
    resolve_model_config,
)
from llm import get_llm, answer_followup, build_followup_context
# The investigation lives in pipeline.py, which the MCP server calls too. This
# page supplies the widgets, the spinners and the panels.
from pipeline import PipelineError, followup_model, run_investigation
from prompts import PRESETS, PRESET_PROMPTS
from store import load_investigations
from langchain_core.messages import HumanMessage, AIMessage
from config import DEPTH_LIMITS, RobinConfig
from health import check_llm_health, check_search_engines, check_tor_proxy


def _render_pipeline_error(stage: str, err: Exception) -> None:
    message = str(err).strip() or err.__class__.__name__
    lower_msg = message.lower()
    hints = [
        "- Confirm the relevant API key is set in your `.env` or shell before launching Streamlit.",
        "- Keys copied from dashboards often include hidden spaces; re-copy if authentication keeps failing.",
        "- Restart the app after updating environment variables so the new values are picked up.",
    ]

    if any(token in lower_msg for token in ("rate limit", "rate_limit", "429", "quota",
                                            "resource has been exhausted", "too many requests")):
        hints.insert(0, "- The model provider is rate-limiting this key. Wait a minute and "
                        "run it again, lower **Max Results to Filter**, or pick another model.")
    elif any(token in lower_msg for token in ("anthropic", "x-api-key", "invalid api key", "authentication")):
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
    """Stop the page and say plainly that nothing was found.

    An empty result is a real answer, so no report is built from whatever
    links happen to be left.
    """
    st.warning("🔍 {}\n\n{}".format(headline, "\n".join(hints)))
    st.stop()


# Cached backend calls. They live here because `st.cache_data` is Streamlit's,
# and the pipeline takes them as injected callables so a repeated query reuses
# the cached search and scrape.
@st.cache_data(ttl=200, show_spinner=False)
def _cached_search(refined_query: str, threads: int):
    return get_search_results_detailed(refined_query, max_workers=threads)


def cached_search_results(refined_query: str, threads: int):
    """The cached search, except an outage: a retry has to search again."""
    outcome = _cached_search(refined_query, threads)
    if engines_unreachable(outcome["stats"]):
        _cached_search.clear(refined_query, threads)
    return outcome


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int, content_chars: int):
    return scrape_multiple(filtered, max_workers=threads,
                           max_return_chars=content_chars)


st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

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


st.sidebar.title("Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown(
    """Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)"""
)
st.sidebar.subheader("Settings")
def _env_is_set(value) -> bool:
    return bool(value and str(value).strip() and "your_" not in str(value))

# Seed session state from .env on first run. This must happen before
# get_model_choices.
_env_cfg = RobinConfig.from_env()
if "custom_api_url" not in st.session_state:
    st.session_state["custom_api_url"] = _env_cfg.custom_api_base_url or ""
if "custom_api_key" not in st.session_state:
    st.session_state["custom_api_key"] = _env_cfg.custom_api_key or ""
if "custom_api_model" not in st.session_state:
    st.session_state["custom_api_model"] = _env_cfg.custom_api_model or ""

# The config for this rerun is the environment, with whatever the user typed
# into the Custom API Provider box layered on top.
_robin_cfg = replace(
    _env_cfg,
    custom_api_base_url=st.session_state["custom_api_url"].strip() or None,
    custom_api_key=st.session_state["custom_api_key"].strip() or None,
    custom_api_model=st.session_state["custom_api_model"].strip() or None,
)

model_options = get_model_choices(_robin_cfg)
model_display_names = get_model_display_names(model_options, _robin_cfg)

# Preselect the newest inexpensive model. The rule lives in llm_utils because
# robin_investigate needs the same answer when nobody names a model.
default_model_index = (model_options.index(default_model(model_options))
                       if model_options else 0)

if not model_options:
    # Distinguish "nothing configured" from "configured but unreachable": a
    # good key with an unreachable provider is a different fix.
    try:
        _configured = model_registry.configured_providers(_robin_cfg)
    except Exception:
        _configured = []
    if _configured:
        st.sidebar.error(
            "⛔ **Could not load models for: {}.**\n\n"
            "The key is set, so this is usually the provider being unreachable: "
            "no network, an outage, or an expired key. Robin falls back to a "
            "bundled model list, but it does not carry every provider.\n\n"
            "Retry once you have a connection, or add a second provider's key. "
            "See TROUBLESHOOTING.md.".format(", ".join(_configured))
        )
    else:
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
# Starting values come from ROBIN_DEFAULT_* when set, already clamped into these
# ranges by config.py; the ranges are the same ones the MCP server advertises.
threads = st.sidebar.slider(
    "Scraping Threads", *DEPTH_LIMITS["threads"], _env_cfg.default_threads,
    key="thread_slider",
)
max_results = st.sidebar.slider(
    "Max Results to Filter", *DEPTH_LIMITS["max_results"], _env_cfg.default_max_results,
    key="max_results_slider",
    help="Cap the number of raw search results passed to the LLM filter step.",
)
max_scrape = st.sidebar.slider(
    "Max Pages to Scrape", *DEPTH_LIMITS["max_scrape"], _env_cfg.default_max_scrape,
    key="max_scrape_slider",
    help="Cap the number of filtered results that get scraped for content.",
)
content_chars = st.sidebar.slider(
    "Content per Page (characters)", *DEPTH_LIMITS["content_chars"],
    _env_cfg.default_content_chars, step=1000,
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
    ("OpenAI",      _robin_cfg.openai_api_key,     True),
    ("Anthropic",   _robin_cfg.anthropic_api_key,  True),
    ("Google",      _robin_cfg.google_api_key,     True),
    ("OpenRouter",  _robin_cfg.openrouter_api_key, True),
    ("Ollama",      _robin_cfg.ollama_base_url,    False),
    ("llama.cpp",   _robin_cfg.llama_cpp_base_url, False),
]
for name, value, is_cloud in _providers:
    if _env_is_set(value):
        st.sidebar.markdown(f"&ensp;✅ **{name}** — configured")
    elif is_cloud:
        st.sidebar.markdown(f"&ensp;⚠️ **{name}** — API key not set")
    else:
        st.sidebar.markdown(f"&ensp;🔵 **{name}** — not configured *(optional)*")

with st.sidebar.expander("⚙️ Prompt Settings"):
    # Labels come from the preset catalog, so the sidebar and the MCP tools name
    # the four domains identically.
    preset_options = {label: key for key, (label, _) in PRESETS.items()}
    preset_placeholders = {
        "threat_intel": "e.g. Pay extra attention to cryptocurrency wallet addresses and exchange names.",
        "ransomware_malware": "e.g. Highlight any references to double-extortion tactics or known ransomware-as-a-service affiliates.",
        "personal_identity": "e.g. Flag any passport or government ID numbers and note which country they appear to be from.",
        "corporate_espionage": "e.g. Prioritize any mentions of source code repositories, API keys, or internal Slack/email dumps.",
    }
    _preset_keys = list(preset_options.values())
    selected_preset_label = st.selectbox(
        "Research Domain",
        list(preset_options.keys()),
        index=(_preset_keys.index(_env_cfg.default_preset)
               if _env_cfg.default_preset in _preset_keys else 0),
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

st.sidebar.divider()
st.sidebar.subheader("Health Checks")

if st.sidebar.button("🔌 Check LLM Connection", use_container_width=True):
    with st.sidebar:
        with st.spinner(f"Testing {model}..."):
            result = check_llm_health(model, _robin_cfg)
        if result["status"] == "up":
            st.sidebar.success(
                f"✅ **{result['provider']}** — Connected ({result['latency_ms']}ms)"
            )
        else:
            st.sidebar.error(
                f"❌ **{result['provider']}** — Failed\n\n{result['error']}"
            )

if st.sidebar.button("🔍 Check Search Engines", use_container_width=True):
    with st.sidebar:
        with st.spinner("Checking Tor proxy..."):
            tor_result = check_tor_proxy()
        if tor_result["status"] == "down":
            st.sidebar.error(
                f"❌ **Tor Proxy** — Not reachable\n\n{tor_result['error']}\n\n"
                "Ensure Tor is running: `sudo systemctl start tor`"
            )
        elif tor_result["status"] != "up":
            st.sidebar.warning(
                f"⏳ **Tor Proxy** — Still starting\n\n{tor_result['error']}\n\n"
                "The engines cannot be reached until Tor has bootstrapped."
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
            # Some saved files carry only the display label, not the preset key,
            # so the label is mapped back to its key for follow-ups.
            _saved_preset = _saved.get("preset", "threat_intel")
            if _saved.get("preset_key") in PRESETS:
                _preset_key = _saved["preset_key"]
            elif _saved_preset in preset_options:
                _preset_key = preset_options[_saved_preset]
            elif _saved_preset in preset_options.values():
                _preset_key = _saved_preset
            else:
                _preset_key = "threat_intel"
            # The same keys a fresh run stores below, with None where the file
            # lacks a value: the follow-up chat reads content_chars and
            # max_scrape from either shape.
            st.session_state["active_investigation"] = {
                "query": _saved.get("query", ""),
                "refined": _saved.get("refined_query", ""),
                "model": _saved.get("model", ""),
                "preset": _preset_key,
                "preset_label": _saved.get("preset", ""),
                "sources": _saved.get("sources", []),
                "scraped": None,  # The raw scrape is not saved to disk.
                "summary": _saved.get("summary", ""),
                "results_count": _saved.get("results_count",
                                            len(_saved.get("sources", []))),
                "content_chars": _saved.get("content_chars"),
                "max_scrape": _saved.get("max_scrape"),
                "timestamp": _saved.get("timestamp", ""),
            }
            st.session_state["chat_history"] = []
            # The saved record carries the pivots, so a reloaded investigation
            # offers the same follow-up searches as the run that wrote it.
            st.session_state["pivot_suggestions"] = list(_saved.get("pivots") or [])
            st.rerun()
else:
    st.sidebar.caption("No saved investigations yet.")


_, logo_col, _ = st.columns(3)
with logo_col:
    st.image(".github/assets/robin_logo.png", width=200)

with st.form("search_form", clear_on_submit=True):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "Enter Dark Web Search Query",
        placeholder="Enter Dark Web Search Query",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("Run")

status_slot = st.empty()
_stat_cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in _stat_cols]
notes_placeholder = st.empty()
sources_placeholder = st.empty()
findings_placeholder = st.empty()


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

    # One click on a suggested pivot runs it as a new investigation.
    pivots = st.session_state.get("pivot_suggestions", [])
    if pivots:
        st.caption("Suggested pivots — click to run as a new investigation:")
        pivot_cols = st.columns(len(pivots))
        for i, (col, pq) in enumerate(zip(pivot_cols, pivots)):
            if col.button(f"🔎 {pq}", key=f"pivot_{i}", use_container_width=True):
                st.session_state["pivot_query"] = pq
                st.rerun()

    for turn in st.session_state.get("chat_history", []):
        with st.chat_message(turn.get("role", "assistant")):
            st.markdown(turn.get("content", ""))

    if st.session_state.get("chat_history"):
        if st.button("🧹 Clear chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()

    # A follow-up is answered from this investigation's context.
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
                # The stored model is provenance. A report an agent saved
                # stores "host", which is not a model this page can build, so
                # the follow-up runs on the sidebar's model instead.
                f_llm = get_llm(followup_model(
                    inv.get("model"), model,
                    lambda name: resolve_model_config(name, _robin_cfg) is not None,
                ), _robin_cfg)
                f_llm.callbacks = [BufferedStreamingHandler(ui_callback=_emit)]
                answer = answer_followup(
                    f_llm, followup, context, history=history,
                    preset=inv.get("preset", "threat_intel"),
                )
                # Reasoning models stream nothing, so fall back to the return value.
                if not acc["text"].strip() and answer:
                    acc["text"] = answer
                    answer_slot.markdown(answer)
            except Exception as e:
                acc["text"] = f"⚠️ Failed to answer follow-up: {e}"
                answer_slot.markdown(acc["text"])

        st.session_state.setdefault("chat_history", [])
        st.session_state["chat_history"].append({"role": "user", "content": followup})
        st.session_state["chat_history"].append({"role": "assistant", "content": acc["text"]})


_STAGE_LABELS = {
    "load_llm": "🔄 Loading LLM...",
    "refine": "🔄 Refining query...",
    "search": "🔍 Searching dark web...",
    "filter": "🗂️ Filtering results...",
    "scrape": "📜 Scraping content...",
    "summarize": "✍️ Generating summary...",
    "pivots": "💡 Suggesting pivots...",
    "save": "💾 Saving investigation...",
}


class _StageIndicator:
    """One spinner at a time in the status slot, driven by the pipeline.

    The investigation is one blocking call, so the stage callback enters and
    closes the spinner's context managers by hand instead of a `with` block.
    """

    def __init__(self, slot):
        self._slot = slot
        self._stack = None

    def show(self, label: str) -> None:
        self.close()
        if not label:
            return
        stack = ExitStack()
        stack.enter_context(self._slot.container())
        stack.enter_context(st.spinner(label))
        self._stack = stack

    def close(self) -> None:
        if self._stack is not None:
            self._stack.close()
            self._stack = None


def _render_stat(slot, title, value) -> None:
    slot.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>{title}</p><p>{value}</p></div>",
        unsafe_allow_html=True,
    )


class _StatTiles:
    """The three counters: "…" while a tile's stage runs, its value once done."""

    _ORDER = tuple(_STAGE_LABELS)
    _TILES = (
        ("Refined Query", "refine", lambda inv: inv.refined),
        ("Search Results", "search", lambda inv: len(inv.results)),
        ("Filtered Results", "filter", lambda inv: len(inv.filtered)),
    )

    def __init__(self, slots):
        self._slots = slots
        self._reached = -1

    def stage_started(self, stage: str, inv) -> None:
        if stage in self._ORDER:
            self._reached = self._ORDER.index(stage)
        self._render(inv, running=True)

    def finish(self, inv) -> None:
        self._render(inv, running=False)

    def fail(self) -> None:
        """Clear the tile whose stage failed, so no "…" is left behind."""
        for slot, (_, stage, _) in zip(self._slots, self._TILES):
            if self._ORDER.index(stage) == self._reached:
                slot.empty()

    def _render(self, inv, running: bool) -> None:
        for slot, (title, stage, value) in zip(self._slots, self._TILES):
            position = self._ORDER.index(stage)
            if position < self._reached or (position == self._reached and not running):
                _render_stat(slot, title, value(inv))
            elif position == self._reached:
                _render_stat(slot, title, "…")


# A run is triggered by a submitted query OR a one-click pivot from the chat panel.
_pivot_query = st.session_state.pop("pivot_query", None)
_active_query = _pivot_query or query
_do_run = bool(_active_query) and (run_button or _pivot_query is not None)

if _do_run:
    query = _active_query
    for k in ["active_investigation", "chat_history", "pivot_suggestions"]:
        st.session_state.pop(k, None)

    _indicator = _StageIndicator(status_slot)
    _tiles = _StatTiles((p1, p2, p3))
    _summary_view = {"slot": None, "text": ""}

    def _on_stage(stage: str, inv) -> None:
        # The findings panel opens as the summary starts.
        if stage == "summarize" and _summary_view["slot"] is None:
            with findings_placeholder.container():
                st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
                _summary_view["slot"] = st.empty()
        _tiles.stage_started(stage, inv)
        _indicator.show(_STAGE_LABELS.get(stage, ""))

    def _on_token(chunk: str) -> None:
        _summary_view["text"] += chunk
        if _summary_view["slot"] is not None:
            _summary_view["slot"].markdown(_summary_view["text"])

    try:
        investigation = run_investigation(
            _robin_cfg, query, model,
            preset=selected_preset,
            custom_instructions=custom_instructions,
            max_results=max_results,
            max_scrape=max_scrape,
            content_chars=content_chars,
            threads=threads,
            on_stage=_on_stage,
            on_token=_on_token,
            search_fn=cached_search_results,
            scrape_fn=cached_scrape_multiple,
            preset_label=selected_preset_label,
        )
    except PipelineError as e:
        _tiles.fail()
        _render_pipeline_error(e.action, e.original)
    finally:
        _indicator.close()

    _tiles.finish(investigation)

    if investigation.status == "engines_unreachable":
        _render_no_results(
            "No search engine answered, so nothing was searched.",
            [
                "- This is not an empty result: the search never ran.",
                "- Run **Check Search Engines** in the sidebar to see which are down.",
                "- Confirm Tor is running and reachable on `socks5h://127.0.0.1:9050`.",
            ],
        )

    if investigation.status == "no_results":
        _render_no_results(
            "No dark web results came back for this query.",
            [
                "- Try broader or differently worded search terms.",
                "- Run **Check Search Engines** in the sidebar; onion engines have irregular uptime.",
                "- Confirm Tor is running and reachable on `socks5h://127.0.0.1:9050`.",
            ],
        )

    if investigation.status == "nothing_relevant":
        _render_no_results(
            "Found {} raw links, but none of them matched this query.".format(
                len(investigation.results)
            ),
            [
                "- The engines that responded returned nothing relevant to these terms.",
                "- Try broader terms, or a different phrasing of the same question.",
                "- Robin stops here on purpose rather than summarizing unrelated pages.",
            ],
        )

    if investigation.status == "nothing_readable":
        _render_no_results(
            "Found {} relevant results, but none of the pages could be read "
            "over Tor right now.".format(len(investigation.filtered)),
            [
                "- Onion services have irregular uptime; the same pages often answer a few minutes later.",
                "- Retry this investigation in a few minutes.",
                "- Run **Check Search Engines** in the sidebar to confirm Tor is healthy.",
                "- Raise **Max Pages to Scrape** so more candidates are tried.",
            ],
        )

    with notes_placeholder.container():
        with st.expander("📋 Notes", expanded=False):
            st.markdown(f"**Refined Query:** `{investigation.refined}`")
            st.markdown(f"**Model:** `{model}` &nbsp;&nbsp; **Domain:** {selected_preset_label}")
            st.markdown(
                f"**Results found:** {len(investigation.results)} &nbsp;&nbsp; "
                f"**Filtered to:** {len(investigation.filtered)} &nbsp;&nbsp; "
                f"**Scraped:** {len(investigation.scraped)}"
            )

    with sources_placeholder.container():
        with st.expander(f"🔗 Sources ({len(investigation.filtered)} results)", expanded=False):
            for i, item in enumerate(investigation.filtered, 1):
                title = item.get("title", "Untitled")
                link = item.get("link", "")
                st.markdown(f"{i}. [{title}]({link})")

    with findings_placeholder.container():
        st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
        st.markdown(investigation.summary)
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(investigation.summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)

    if investigation.saved_as:
        status_slot.success(
            f"✔️ Pipeline completed successfully! Investigation saved as `{investigation.saved_as}`"
        )
    else:
        # The report is on the page and downloadable; only the copy on disk is
        # missing, and that is a mount permission problem with a known fix.
        status_slot.warning(
            "✔️ Pipeline completed, but the investigation could not be saved to disk.\n\n"
            'See "Saved investigations fail with permission denied on Linux" in '
            "TROUBLESHOOTING.md."
        )

    # Persist as the active investigation so it survives chat reruns.
    st.session_state["active_investigation"] = {
        "query": query,
        "refined": investigation.refined,
        "model": model,
        "preset": selected_preset,
        "preset_label": selected_preset_label,
        "sources": investigation.filtered,
        "scraped": investigation.scraped,
        "summary": investigation.summary,
        "results_count": len(investigation.results),
        "content_chars": content_chars,
        "max_scrape": max_scrape,
        # Both shapes carry the same keys. This one stays empty because the banner
        # above the chat panel only dates an investigation loaded from disk.
        "timestamp": "",
    }
    st.session_state["chat_history"] = []
    st.session_state["pivot_suggestions"] = investigation.pivots

    _render_chat_panel(st.session_state["active_investigation"])

# Returning visit (no run this pass, e.g. after a chat submit or a loaded
# investigation): render the active investigation and its chat panel.
elif st.session_state.get("active_investigation"):
    _inv = st.session_state["active_investigation"]
    _ts = _inv.get("timestamp")
    st.info(f"📂 **{_inv.get('query', '')}**" + (f" — {_ts[:16]}" if _ts else ""))
    _render_investigation_body(_inv)
    _render_chat_panel(_inv)
