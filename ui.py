import base64
import streamlit as st
from datetime import datetime
from scrape import scrape_multiple, scrape_single
from search import get_search_results, is_tor_running
from llm_utils import BufferedStreamingHandler
from llm import get_llm, refine_query, filter_results, generate_summary


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

# Custom CSS for styling (glassmorphism-inspired)
st.markdown(
    """
    <style>
            :root { --accent: #FF4B4B; }
            .fade-in { animation: fadeIn 0.6s ease-in-out; }
            @keyframes fadeIn { from { opacity: 0; translate: 0 8px;} to { opacity: 1; translate: 0 0;} }
            .hover-scale { transition: transform 200ms ease, box-shadow 200ms ease; }
            .hover-scale:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.25); }
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
            .glass {
                background: rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.15);
                box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                padding: 10px 12px;
                margin-bottom: 10px;
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
from llm import missing_model_env

# Advanced UI/UX preferences
st.sidebar.subheader("UI Preferences")
show_detailed_progress = st.sidebar.toggle("Detailed scraping progress (slower)", value=False, help="Shows per-URL scraping progress; disables multi-threaded scraping for accuracy.")

model = st.sidebar.selectbox(
    "Select LLM Model",
    ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"],
    key="model_select",
)
missing = missing_model_env(model)
if missing:
    st.sidebar.warning(f"Missing: {', '.join(missing)}")
else:
    st.sidebar.info("Model ready")

threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")


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

# Display a status message
status_slot = st.empty()
# Pre-allocate three placeholders-one per card
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]
# Stage progress
stage_progress = st.progress(0, text="Idle")
# Summary placeholders
summary_container_placeholder = st.empty()


# Process the query
if run_button and query:
    # clear old state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        st.session_state.pop(k, None)

    # Stage 1 - Load LLM
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            try:
                llm = get_llm(model)
            except ValueError as e:
                st.error(str(e))
                st.stop()
            if not is_tor_running():
                st.warning("Tor SOCKS proxy not detected at 127.0.0.1:9050. Searches may return empty.")

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            st.session_state.refined = refine_query(llm, query)
    p1.container(border=True).markdown(
        f"<div class='glass colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )
    stage_progress.progress(20, text="Query refined")

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
    p2.container(border=True).markdown(
        f"<div class='glass colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )
    stage_progress.progress(40, text="Search completed")

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results
            )
    p3.container(border=True).markdown(
        f"<div class='glass colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )
    stage_progress.progress(55, text="Results filtered")

    # New: let the user select which results to scrape
    options = [f"{i+1}. {item['title'][:60]}" for i, item in enumerate(st.session_state.filtered)]
    idx_map = {f"{i+1}. {item['title'][:60]}": i for i, item in enumerate(st.session_state.filtered)}
    selection = st.multiselect(
        "Select results to scrape", options, default=options, help="Unselect to skip scraping specific results."
    )
    selected = [st.session_state.filtered[idx_map[label]] for label in selection]

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            st.session_state.scraped = cached_scrape_multiple(
                selected, threads
            )
    stage_progress.progress(75, text="Scraping complete")

    # Stage 6 - Summarize
    # 6a) Prepare session state for streaming text
    st.session_state.streamed_summary = ""

    # If detailed progress is enabled, run scraping sequentially with progress updates
    if show_detailed_progress:
        prog = st.progress(0, text="Scraping in progress...")
        scraped = {}
        for i, item in enumerate(selected, start=1):
            url, content = scrape_single(item)
            scraped[url] = content
            prog.progress(int(i/len(selected)*100), text=f"Scraping {i}/{len(selected)}")
        st.session_state.scraped = scraped
        stage_progress.progress(75, text="Scraping complete")

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with summary_container_placeholder.container():
        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
        with hdr_col:
            st.subheader(":red[Investigation Summary]", anchor=None, divider="gray")
        summary_slot = st.empty()

    # Tabs for professional layout
    t1, t2, t3 = st.tabs(["Overview", "Sources", "Artifacts (JSON)"])

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)
    stage_progress.progress(95, text="Summary generated")

    # Show summary in Overview tab
    with t1:
        st.markdown(st.session_state.streamed_summary)

    with btn_col:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)
    # Provide CSV/JSON export of sources
    import json, pandas as pd
    sources_df = pd.DataFrame([
        {"url": url, "excerpt": text} for url, text in st.session_state.scraped.items()
    ])

    with t2:
        st.dataframe(sources_df, use_container_width=True, hide_index=True)

    with t3:
        st.json([{ "url": u, "excerpt": t } for u, t in st.session_state.scraped.items()])

    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        st.download_button(
            label="Download sources (CSV)",
            data=sources_df.to_csv(index=False).encode("utf-8"),
            file_name="sources.csv",
            mime="text/csv",
        )
    with exp_col2:
        st.download_button(
            label="Download sources (JSON)",
            data=json.dumps(sources_df.to_dict(orient="records"), ensure_ascii=False, indent=2),
            file_name="sources.json",
            mime="application/json",
        )

    stage_progress.progress(100, text="Done")
    status_slot.success("✔️ Pipeline completed successfully!")
