
import base64
import json
import streamlit as st
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrape import scrape_multiple
from search import get_search_results, get_deep_search_results
from llm_utils import get_model_choices
from llm import (
    get_llm,
    refine_query,
    filter_results,
    generate_mode_summary,
    PRESET_PROMPTS,
)
from agent_orchestrator import InvestigationOrchestrator
from agents import list_available_agents, get_agent
from config import (
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    GOOGLE_API_KEY,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
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


# --- Investigation persistence ---

INVESTIGATIONS_DIR = Path("investigations")
SESSIONS_DIR = Path("sessions")


def save_investigation(query: str, refined_query: str, model: str, preset_label: str, sources: list, summary) -> str:
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


def _get_session_id() -> str:
    sid = st.session_state.get("robin_session_id")
    if sid:
        return sid
    sid = datetime.now().strftime("%Y%m%d") + "-" + str(uuid4())[:8]
    st.session_state["robin_session_id"] = sid
    return sid


def _session_file(session_id: str) -> Path:
    SESSIONS_DIR.mkdir(exist_ok=True)
    return SESSIONS_DIR / f"session_{session_id}.json"


def load_session_history(session_id: str) -> list:
    fpath = _session_file(session_id)
    if not fpath.exists():
        return []
    try:
        payload = json.loads(fpath.read_text())
        return payload.get("messages", []) if isinstance(payload, dict) else []
    except Exception:
        return []


def append_session_history(session_id: str, record: dict) -> None:
    fpath = _session_file(session_id)
    existing = {"session_id": session_id, "messages": []}
    if fpath.exists():
        try:
            loaded = json.loads(fpath.read_text())
            if isinstance(loaded, dict):
                existing = loaded
                existing.setdefault("messages", [])
        except Exception:
            pass
    existing["messages"].append(record)
    existing["updated_at"] = datetime.now().isoformat()
    fpath.write_text(json.dumps(existing, indent=2))


# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query.replace(" ", "+"), max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple(filtered, max_workers=threads)


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

model_options = get_model_choices()
default_model_index = (
    next(
        (idx for idx, name in enumerate(model_options) if name.lower() == "gpt4o"),
        0,
    )
    if model_options
    else 0
)

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
    index=default_model_index,
    key="model_select",
)
if any(name not in {"gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"} for name in model_options):
    st.sidebar.caption("Locally detected Ollama models are automatically added to this list.")
threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")
max_results = st.sidebar.slider(
    "Max Results to Filter", 10, 100, 50, key="max_results_slider",
    help="Cap the number of raw search results passed to the LLM filter step.",
)
max_scrape = st.sidebar.slider(
    "Max Pages to Scrape", 3, 20, 10, key="max_scrape_slider",
    help="Cap the number of filtered results that get scraped for content.",
)
deep_research_mode = st.sidebar.toggle(
    "Deep Research Search",
    value=True,
    help="Expand discovery by recursively crawling onion links from initial search results.",
)
research_depth = st.sidebar.slider(
    "Deep Crawl Depth",
    0,
    2,
    1,
    help="0 disables crawl expansion, 1-2 increases coverage and runtime.",
)

multi_agent_mode = st.sidebar.toggle(
    "🔬 Multi-Agent Investigation Mode",
    value=False,
    help="Deploy specialized agent team (REAPER→TRACE→LEDGER→FLUX→MASON→VEIL→BISHOP→GHOST) for comprehensive analysis.",
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
            st.session_state["loaded_investigation"] = saved_investigations[selected_inv_idx]
            st.rerun()
else:
    st.sidebar.caption("No saved investigations yet.")

st.sidebar.divider()
st.sidebar.subheader("💬 Session History")
active_session_id = _get_session_id()
session_history = load_session_history(active_session_id)
st.sidebar.caption(f"Session: {active_session_id}")
if session_history:
    for idx, item in enumerate(reversed(session_history[-6:]), 1):
        ts = item.get("timestamp", "")[:16].replace("T", " ")
        q = item.get("query", "")[:45]
        st.sidebar.markdown(f"{idx}. {ts} - {q}")
else:
    st.sidebar.caption("No messages in this session yet.")


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

# Display loaded investigation (if any)
if "loaded_investigation" in st.session_state and not run_button:
    inv = st.session_state["loaded_investigation"]
    st.info(f"📂 **{inv['query']}** — {inv['timestamp'][:16]}")
    with st.expander("📋 Notes", expanded=False):
        st.markdown(f"**Refined Query:** `{inv['refined_query']}`")
        st.markdown(f"**Model:** `{inv['model']}` &nbsp;&nbsp; **Domain:** {inv['preset']}")
        st.markdown(f"**Sources:** {len(inv['sources'])}")
    with st.expander(f"🔗 Sources ({len(inv['sources'])} results)", expanded=False):
        for i, item in enumerate(inv["sources"], 1):
            title = item.get("title", "Untitled")
            link = item.get("link", "")
            st.markdown(f"{i}. [{title}]({link})")
    st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
    summary_payload = inv.get("summary")
    if isinstance(summary_payload, dict):
        tab_filtered, tab_risky = st.tabs(["Filtered", "Risky"])
        with tab_filtered:
            st.markdown(summary_payload.get("filtered", "No filtered output saved."))
        with tab_risky:
            st.markdown(summary_payload.get("risky", "No risky output saved."))
    else:
        st.markdown(summary_payload or "No summary found.")
    if st.button("✖ Clear"):
        del st.session_state["loaded_investigation"]
        st.rerun()

# Status + result section placeholders
status_slot = st.empty()
notes_placeholder = st.empty()
sources_placeholder = st.empty()
findings_placeholder = st.empty()


# Process the query
if run_button and query:
    # Clear any loaded investigation and old pipeline state
    st.session_state.pop("loaded_investigation", None)
    for k in ["refined", "results", "filtered", "scraped", "filtered_summary", "risky_summary", "multi_agent_report"]:
        st.session_state.pop(k, None)

    # Stage 1 - Load LLM
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            try:
                llm = get_llm(model)
            except Exception as e:
                _render_pipeline_error("load the selected LLM", e)

    # =============================================================================
    # MULTI-AGENT INVESTIGATION MODE
    # =============================================================================
    if multi_agent_mode:
        with status_slot.container():
            st.info("🔬 Deploying multi-agent investigation team...")
        
        # Initialize orchestrator
        orchestrator = InvestigationOrchestrator(llm)
        
        # Stage A - Initial search and scrape (same as standard mode)
        with status_slot.container():
            with st.spinner("🔍 Initial search (multi-agent mode)..."):
                try:
                    st.session_state.refined = refine_query(llm, query)
                except Exception as e:
                    _render_pipeline_error("refine query", e)
        
        with status_slot.container():
            search_label = "🔍 Searching dark web (deep + multi-agent)..." if deep_research_mode else "🔍 Searching dark web..."
            with st.spinner(search_label):
                if deep_research_mode:
                    st.session_state.results = get_deep_search_results(
                        st.session_state.refined,
                        max_workers=threads,
                        crawl_depth=research_depth,
                        max_seed_links=max_results,
                    )
                else:
                    st.session_state.results = cached_search_results(
                        st.session_state.refined, threads
                    )
        
        if len(st.session_state.results) > max_results:
            st.session_state.results = st.session_state.results[:max_results]
        
        with status_slot.container():
            with st.spinner("🗂️ Filtering results..."):
                st.session_state.filtered = filter_results(
                    llm, st.session_state.refined, st.session_state.results
                )
        
        if len(st.session_state.filtered) > max_scrape:
            st.session_state.filtered = st.session_state.filtered[:max_scrape]
        
        with status_slot.container():
            with st.spinner("📜 Scraping content..."):
                st.session_state.scraped = cached_scrape_multiple(
                    st.session_state.filtered, threads
                )
        
        # Stage B - Deploy agent team
        combined_scraped_data = " ".join(
            [f"{url}: {content}" for url, content in st.session_state.scraped.items()]
        )
        
        orchestrator.initialize_context(query, combined_scraped_data)
        
        with findings_placeholder.container():
            st.subheader("🔬 Multi-Agent Investigation", anchor=None, divider="gray")
            agent_progress = st.empty()
            agent_container = st.container()
        
        with status_slot.container():
            with st.spinner("🔬 Deploying agent team (8 agents in sequence)..."):
                try:
                    # Show agent roster
                    agent_status = st.empty()
                    agent_cards = []
                    
                    investigation_result = orchestrator.run_dark_web_investigation_workflow()
                    
                    st.session_state.multi_agent_report = investigation_result
                    
                    with agent_container:
                        # Display agent findings in cards
                        cols = st.columns(2)
                        for idx, agent_result in enumerate(investigation_result["workflow"]):
                            col = cols[idx % 2]
                            with col:
                                agent_name = agent_result.get("agent", "Unknown")
                                status_icon = "✅" if agent_result.get("status") == "success" else "❌"
                                with st.expander(f"{status_icon} {agent_name}"):
                                    if agent_result.get("status") == "success":
                                        st.markdown(agent_result.get("findings", "No findings"))
                                    else:
                                        st.error(f"Error: {agent_result.get('error', 'Unknown error')}")
                        
                        st.divider()
                        st.subheader("📊 Integrated Multi-Agent Report")
                        st.markdown(investigation_result.get("final_report", "Report generation failed."))
                        
                        # Workflow log
                        with st.expander("📋 Workflow Log"):
                            for entry in investigation_result.get("timeline", []):
                                st.text(f"{entry['timestamp']} — {entry['agent']}: {entry['status']}")
                
                except Exception as e:
                    _render_pipeline_error("run multi-agent investigation", e)
        
        # Save multi-agent investigation
        _fname = save_investigation(
            query=query,
            refined_query=st.session_state.refined,
            model=model,
            preset_label=f"Multi-Agent ({selected_preset_label})",
            sources=st.session_state.filtered,
            summary={
                "multi_agent_report": investigation_result.get("final_report", ""),
                "agent_findings": investigation_result.get("workflow", []),
            },
        )
        
        append_session_history(
            active_session_id,
            {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "refined_query": st.session_state.refined,
                "model": model,
                "preset": "multi-agent",
                "mode": "multi-agent",
                "source_count": len(st.session_state.filtered),
            },
        )
        
        status_slot.success(f"✔️ Multi-agent investigation completed! Saved as `{_fname}`")
    
    # =============================================================================
    # STANDARD DUAL-OUTPUT MODE (Non-Multi-Agent)
    # =============================================================================
    else:

    # Standard dual-output mode - indented under else
        # Stage 2 - Refine query
        with status_slot.container():
            with st.spinner("🔄 Refining query..."):
                try:
                    st.session_state.refined = refine_query(llm, query)
                except Exception as e:
                    _render_pipeline_error("refine the query", e)

        # Stage 3 - Search dark web
        with status_slot.container():
            search_label = "🔍 Searching dark web (deep mode)..." if deep_research_mode else "🔍 Searching dark web..."
            with st.spinner(search_label):
                if deep_research_mode:
                    st.session_state.results = get_deep_search_results(
                        st.session_state.refined,
                        max_workers=threads,
                        crawl_depth=research_depth,
                        max_seed_links=max_results,
                    )
                else:
                    st.session_state.results = cached_search_results(
                        st.session_state.refined, threads
                    )
        # Cap results before LLM filter step
        if len(st.session_state.results) > max_results:
            st.session_state.results = st.session_state.results[:max_results]

        # Stage 4 - Filter results
        with status_slot.container():
            with st.spinner("🗂️ Filtering results..."):
                st.session_state.filtered = filter_results(
                    llm, st.session_state.refined, st.session_state.results
                )
        # Cap filtered results before scraping
        if len(st.session_state.filtered) > max_scrape:
            st.session_state.filtered = st.session_state.filtered[:max_scrape]

        # Stage 5 - Scrape content
        with status_slot.container():
            with st.spinner("📜 Scraping content..."):
                st.session_state.scraped = cached_scrape_multiple(
                    st.session_state.filtered, threads
                )

        # Stage 6 - Dual summarize in parallel (Filtered + Risky)
        st.session_state.filtered_summary = ""
        st.session_state.risky_summary = ""

        with findings_placeholder.container():
            st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
            summary_status = st.info("Running Filtered and Risky analysis in parallel...")

        with status_slot.container():
            with st.spinner("✍️ Generating Filtered + Risky summaries..."):
                try:
                    llm_filtered = get_llm(model)
                    llm_risky = get_llm(model)
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        futures = {
                            executor.submit(
                                generate_mode_summary,
                                llm_filtered,
                                query,
                                st.session_state.scraped,
                                "filtered",
                                selected_preset,
                                custom_instructions,
                            ): "filtered",
                            executor.submit(
                                generate_mode_summary,
                                llm_risky,
                                query,
                                st.session_state.scraped,
                                "risky",
                                selected_preset,
                                custom_instructions,
                            ): "risky",
                        }

                        for future in as_completed(futures):
                            mode = futures[future]
                            result = future.result()
                            if mode == "filtered":
                                st.session_state.filtered_summary = result
                            else:
                                st.session_state.risky_summary = result
                except Exception as e:
                    _render_pipeline_error("generate dual summaries", e)

        summary_status.success("Parallel analysis completed.")

        dual_summary_payload = {
            "filtered": st.session_state.filtered_summary,
            "risky": st.session_state.risky_summary,
        }

        # Save investigation
        _fname = save_investigation(
            query=query,
            refined_query=st.session_state.refined,
            model=model,
            preset_label=selected_preset_label,
            sources=st.session_state.filtered,
            summary=dual_summary_payload,
        )

        append_session_history(
            active_session_id,
            {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "refined_query": st.session_state.refined,
                "model": model,
                "preset": selected_preset,
                "deep_research": deep_research_mode,
                "research_depth": research_depth,
                "summary": dual_summary_payload,
                "source_count": len(st.session_state.filtered),
            },
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
                st.markdown(
                    f"**Search Mode:** {'Deep Research' if deep_research_mode else 'Standard'} &nbsp;&nbsp; "
                    f"**Depth:** {research_depth}"
                )

        with sources_placeholder.container():
            with st.expander(f"🔗 Sources ({len(st.session_state.filtered)} results)", expanded=False):
                for i, item in enumerate(st.session_state.filtered, 1):
                    title = item.get("title", "Untitled")
                    link = item.get("link", "")
                    st.markdown(f"{i}. [{title}]({link})")

        with findings_placeholder.container():
            st.subheader(":red[🔎 Findings]", anchor=None, divider="gray")
            tab_filtered, tab_risky = st.tabs(["Filtered", "Risky"])
            with tab_filtered:
                st.markdown(st.session_state.filtered_summary)
            with tab_risky:
                st.markdown(st.session_state.risky_summary)
            now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            fname = f"summary_{now}.md"
            combined = (
                "# Filtered\n\n"
                + st.session_state.filtered_summary
                + "\n\n# Risky\n\n"
                + st.session_state.risky_summary
            )
            b64 = base64.b64encode(combined.encode()).decode()
            href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
            st.markdown(href, unsafe_allow_html=True)

        status_slot.success(f"✔️ Pipeline completed successfully! Investigation saved as `{_fname}`")
