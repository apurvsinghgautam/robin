import base64
import streamlit as st
import time
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm_utils import BufferedStreamingHandler, get_model_choices
from llm import get_llm, refine_query, filter_results, generate_summary
from logger_utils import get_logger

# Initialize logger
logger = get_logger()

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
    layout="wide",
)

# Custom CSS for styling
st.markdown(
    """
    <style>
            .colHeight {
                max-height: 40vh;
                overflow-y: auto;
                text-align: center;
            }
            .pTitle {
                font-weight: bold;
                color: #FF4B4B;
                margin-bottom: 0.5em;
            }
            .aStyle {
                font-size: 18px;
                font-weight: bold;
                padding: 5px;
                padding-left: 0px;
                text-align: center;
            }
            .log-entry {
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                padding: 2px 0;
            }
            .log-info { color: #1f77b4; }
            .log-warning { color: #ff7f0e; }
            .log-error { color: #d62728; }
            .log-debug { color: #9467bd; }
            .api-data {
                background-color: #f0f0f0;
                padding: 10px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                max-height: 200px;
                overflow-y: auto;
            }
    </style>""",
    unsafe_allow_html=True,
)

# Initialize session state
if "api_data_log" not in st.session_state:
    st.session_state.api_data_log = []
if "progress_data" not in st.session_state:
    st.session_state.progress_data = {
        "current_stage": 0,
        "total_stages": 6,
        "stage_names": [
            "Loading LLM",
            "Refining Query",
            "Searching Dark Web",
            "Filtering Results",
            "Scraping Content",
            "Generating Summary"
        ],
        "start_time": None,
        "stage_times": []
    }

# Sidebar
st.sidebar.title("Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown(
    """Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)"""
)

# Settings Section
st.sidebar.subheader("⚙️ Settings")

# Get model choices (refresh if button clicked)
refresh_models = st.sidebar.button("🔄 Refresh Models", help="Refresh the list of available Ollama models", use_container_width=True)

if refresh_models:
    st.cache_data.clear()
    logger.info("Refreshing model list...")
    st.sidebar.success("Models refreshed!")

model_options = get_model_choices(refresh_ollama=True)
default_model_index = (
    next(
        (idx for idx, name in enumerate(model_options) if name.lower() == "gpt-5-mini"),
        0,
    )
    if model_options
    else 0
)
model = st.sidebar.selectbox(
    "🤖 LLM Model",
    model_options,
    index=default_model_index,
    key="model_select",
    help="Select the LLM model to use. Ollama models are automatically detected when installed."
)

# Show which models are Ollama with better styling
ollama_models = [m for m in model_options if m not in [
    "gpt-4.1", "gpt-5.1", "gpt-5-mini", "gpt-5-nano",
    "claude-sonnet-4-5", "claude-sonnet-4-0",
    "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro",
    "gpt-5.1-openrouter", "gpt-5-mini-openrouter", "claude-sonnet-4.5-openrouter", "grok-4.1-fast-openrouter"
]]
if ollama_models:
    st.sidebar.info(f"🦙 **{len(ollama_models)} local Ollama model(s)** detected automatically")

st.sidebar.divider()

threads = st.sidebar.slider(
    "🧵 Scraping Threads", 
    1, 16, 4, 
    key="thread_slider",
    help="Number of parallel threads to use for scraping. More threads = faster but more resource intensive."
)

# Logging section in sidebar
st.sidebar.divider()
st.sidebar.subheader("📋 Logs")
show_logs = st.sidebar.checkbox("Show Logs", value=False, key="show_logs", help="Display real-time logs in the main area")
if st.sidebar.button("🗑️ Clear Logs", use_container_width=True):
    logger.clear_logs()
    st.session_state.api_data_log = []
    st.sidebar.success("Logs cleared!")

# Main UI - logo and input
_, logo_col, _ = st.columns(3)
with logo_col:
    try:
        st.image(".github/assets/robin_logo.png", width=200)
    except:
        st.title("🕵️‍♂️ Robin")

# Display text box and button with keyboard shortcut hint
st.caption("💡 Press Enter to submit (or click Run button)")
with st.form("search_form", clear_on_submit=False):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "Enter Dark Web Search Query",
        placeholder="Enter Dark Web Search Query (Press Enter to submit)",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("Run", use_container_width=True)

# Progress tracking
progress_container = st.empty()
progress_bar = st.empty()
progress_text = st.empty()

# API Data Display
api_data_container = st.expander("📡 API Data Being Sent", expanded=False)

# Display a status message
status_slot = st.empty()
# Pre-allocate three placeholders-one per card
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]
# Summary placeholders
summary_container_placeholder = st.empty()

# Logs display area
logs_display_area = st.empty()

def update_progress(stage: int, message: str = ""):
    """Update progress bar and ETA"""
    progress_data = st.session_state.progress_data
    current_time = time.time()
    
    if stage == 0:
        progress_data["start_time"] = current_time
        progress_data["stage_times"] = []
    
    # Calculate progress percentage
    progress_pct = (stage / progress_data["total_stages"]) * 100
    
    # Calculate ETA
    if stage > 0 and len(progress_data["stage_times"]) > 0:
        avg_stage_time = sum(progress_data["stage_times"]) / len(progress_data["stage_times"])
        remaining_stages = progress_data["total_stages"] - stage
        eta_seconds = avg_stage_time * remaining_stages
        eta_str = f"ETA: {int(eta_seconds)}s"
    else:
        eta_str = "Calculating..."
    
    # Update progress bar
    progress_bar.progress(progress_pct / 100)
    progress_text.text(f"Stage {stage + 1}/{progress_data['total_stages']}: {progress_data['stage_names'][stage]} | {eta_str} | {message}")
    
    # Record stage time
    if stage > 0 and progress_data["start_time"]:
        stage_time = current_time - (progress_data["start_time"] + sum(progress_data["stage_times"]))
        if stage_time > 0:
            progress_data["stage_times"].append(stage_time)

def log_api_data(stage: str, model: str, prompt_type: str, data_preview: str, data_length: int):
    """Log API data for display"""
    entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "stage": stage,
        "model": model,
        "type": prompt_type,
        "preview": data_preview[:300] + "..." if len(data_preview) > 300 else data_preview,
        "length": data_length
    }
    st.session_state.api_data_log.append(entry)
    
    # Update API data display
    with api_data_container:
        st.markdown(f"**{entry['timestamp']}** - {entry['stage']} ({entry['model']})")
        st.markdown(f"*Type:* {entry['type']} | *Length:* {entry['length']} chars")
        st.markdown(f"<div class='api-data'>{entry['preview']}</div>", unsafe_allow_html=True)
        st.divider()

# Process the query
if run_button and query:
    logger.info(f"=== Starting new investigation: '{query}' ===")
    logger.info(f"Model: {model}, Threads: {threads}")
    
    # clear old state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)
    st.session_state.api_data_log = []
    st.session_state.progress_data["start_time"] = None
    st.session_state.progress_data["stage_times"] = []

    # Stage 1 - Load LLM
    update_progress(0, "Initializing model...")
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            start_stage = time.time()
            llm = get_llm(model)
            model_name = getattr(llm, "_robin_model_name", model)
            stage_time = time.time() - start_stage
            logger.info(f"LLM loaded in {stage_time:.2f}s")
    update_progress(1, "Query refinement...")

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            start_stage = time.time()
            st.session_state.refined = refine_query(llm, query, model_name=model_name)
            stage_time = time.time() - start_stage
            logger.info(f"Query refined in {stage_time:.2f}s: '{st.session_state.refined}'")
            
            # Log API data
            log_api_data(
                stage="Query Refinement",
                model=model_name,
                prompt_type="refine_query",
                data_preview=f"Original: {query}\nRefined: {st.session_state.refined}",
                data_length=len(query) + len(st.session_state.refined)
            )
    
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )
    update_progress(2, "Searching...")

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            start_stage = time.time()
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
            stage_time = time.time() - start_stage
            logger.info(f"Search completed in {stage_time:.2f}s: {len(st.session_state.results)} results")
            update_progress(2, f"Found {len(st.session_state.results)} results")
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )
    update_progress(3, f"Filtering {len(st.session_state.results)} results...")

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            start_stage = time.time()
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results, model_name=model_name
            )
            stage_time = time.time() - start_stage
            logger.info(f"Filtering completed in {stage_time:.2f}s: {len(st.session_state.filtered)} filtered")
            
            # Log API data
            log_api_data(
                stage="Result Filtering",
                model=model_name,
                prompt_type="filter_results",
                data_preview=f"Query: {st.session_state.refined}\nResults to filter: {len(st.session_state.results)}",
                data_length=len(str(st.session_state.results))
            )
    
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )
    update_progress(3, f"Filtered to {len(st.session_state.filtered)} results")
    update_progress(4, f"Scraping {len(st.session_state.filtered)} URLs...")

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            start_stage = time.time()
            st.session_state.scraped = cached_scrape_multiple(
                st.session_state.filtered, threads
            )
            stage_time = time.time() - start_stage
            logger.info(f"Scraping completed in {stage_time:.2f}s: {len(st.session_state.scraped)} pages")
            update_progress(4, f"Scraped {len(st.session_state.scraped)} pages")
    update_progress(5, "Generating summary...")

    # Stage 6 - Summarize
    # 6a) Prepare session state for streaming text
    st.session_state.streamed_summary = ""

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with summary_container_placeholder.container():
        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
        with hdr_col:
            st.subheader(":red[Investigation Summary]", anchor=None, divider="gray")
        summary_slot = st.empty()

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            start_stage = time.time()
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped, model_name=model_name)
            stage_time = time.time() - start_stage
            logger.info(f"Summary generated in {stage_time:.2f}s: {len(st.session_state.streamed_summary)} chars")
            
            # Log API data
            content_preview = str(list(st.session_state.scraped.keys())[:3]) if st.session_state.scraped else "No content"
            log_api_data(
                stage="Summary Generation",
                model=model_name,
                prompt_type="generate_summary",
                data_preview=f"Query: {query}\nContent items: {len(st.session_state.scraped)}\nPreview: {content_preview}",
                data_length=sum(len(str(v)) for v in st.session_state.scraped.values()) if st.session_state.scraped else 0
            )

    with btn_col:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)
    
    # Final progress update
    total_time = time.time() - st.session_state.progress_data["start_time"]
    progress_bar.progress(1.0)
    progress_text.text(f"✅ Completed in {total_time:.1f}s")
    status_slot.success("✔️ Pipeline completed successfully!")
    logger.info(f"=== Investigation completed in {total_time:.2f}s ===")

# Display logs if enabled
if show_logs:
    recent_logs = logger.get_recent_logs(limit=50)
    with logs_display_area.container():
        st.subheader("📋 Recent Logs")
        log_container = st.container()
        with log_container:
            for log_entry in recent_logs[-20:]:  # Show last 20
                level_class = f"log-{log_entry['level'].lower()}"
                st.markdown(
                    f"<div class='log-entry {level_class}'>"
                    f"[{log_entry['timestamp']}] {log_entry['level']}: {log_entry['message']}"
                    f"</div>",
                    unsafe_allow_html=True
                )
