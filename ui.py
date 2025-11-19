import base64
import streamlit as st
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm_utils import BufferedStreamingHandler
from llm import get_llm, refine_query, filter_results, generate_summary

# Cache expensive backend calls
@st.cache_data(ttl=600, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query, max_workers=threads)

@st.cache_data(ttl=600, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple(filtered, max_workers=threads)

st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    initial_sidebar_state="expanded",
)

st.markdown(
    """<style>
            .colHeight { max-height: 40vh; overflow-y: auto; text-align: center; }
            .pTitle { font-weight: bold; color: #FF4B4B; margin-bottom: 0.5em; }
            .aStyle { font-size: 18px; font-weight: bold; padding: 5px; text-align: center; }
    </style>""",
    unsafe_allow_html=True,
)

# Sidebar
st.sidebar.title("Robin")
st.sidebar.info("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown("Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/)")
st.sidebar.subheader("Settings")
model = st.sidebar.selectbox(
    "Select LLM Model",
    ["gpt-5.1", "gpt-5-mini", "gpt-5-nano", "gpt-4.1", "claude-sonnet-4-5", "claude-sonnet-4-0", "llama3.1", "llama3.2", "gemma3", "deepseek-r1", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
    key="model_select",
)
threads = st.sidebar.slider("Scraping Threads", 1, 16, 5, key="thread_slider")

# Main UI
_, logo_col, _ = st.columns(3)
with logo_col:
    # Placeholder for logo if exists, otherwise text
    st.markdown("### 🕵️‍♂️ Robin OSINT")

with st.form("search_form", clear_on_submit=False):
    col_input, col_button = st.columns([8, 2])
    query = col_input.text_input("Enter Dark Web Search Query", placeholder="e.g. ransomware leak sites")
    run_button = col_button.form_submit_button("Run Investigation")

status_slot = st.empty()
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]
summary_container = st.empty()

if run_button and query:
    # Clear previous state
    for k in ["refined", "results", "filtered", "scraped", "streamed_summary"]:
        if k in st.session_state:
            del st.session_state[k]

    try:
        # 1. Load LLM
        with status_slot.container():
            with st.spinner("🔄 Loading LLM..."):
                llm = get_llm(model)

        # 2. Refine Query
        with status_slot.container():
            with st.spinner("🔄 Refining query..."):
                st.session_state.refined = refine_query(llm, query)
        p1.container(border=True).markdown(
            f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
            unsafe_allow_html=True
        )

        # 3. Search
        with status_slot.container():
            with st.spinner("🔍 Searching dark web (this may take time)..."):
                st.session_state.results = cached_search_results(st.session_state.refined, threads)
        
        result_count = len(st.session_state.results)
        p2.container(border=True).markdown(
            f"<div class='colHeight'><p class='pTitle'>Found Links</p><p>{result_count}</p></div>",
            unsafe_allow_html=True
        )

        if result_count == 0:
            st.error("No results found. The search engines might be unreachable via Tor right now.")
            st.stop()

        # 4. Filter
        with status_slot.container():
            with st.spinner("🗂️ Filtering relevance..."):
                st.session_state.filtered = filter_results(llm, st.session_state.refined, st.session_state.results)
        
        filtered_count = len(st.session_state.filtered)
        p3.container(border=True).markdown(
            f"<div class='colHeight'><p class='pTitle'>Relevant Links</p><p>{filtered_count}</p></div>",
            unsafe_allow_html=True
        )

        # 5. Scrape
        with status_slot.container():
            with st.spinner(f"📜 Scraping {filtered_count} sites..."):
                st.session_state.scraped = cached_scrape_multiple(st.session_state.filtered, threads)

        if not st.session_state.scraped:
            st.error("Scraping failed. All selected sites were unreachable.")
            st.stop()

        # 6. Summarize
        st.session_state.streamed_summary = ""
        
        def ui_emit(chunk: str):
            st.session_state.streamed_summary += chunk
            summary_slot.markdown(st.session_state.streamed_summary)

        with summary_container.container():
            st.subheader("Investigation Summary", divider="red")
            summary_slot = st.empty()

        with status_slot.container():
            with st.spinner("✍️ Analyzing intelligence..."):
                stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
                llm.callbacks = [stream_handler]
                _ = generate_summary(llm, query, st.session_state.scraped)

        # Download Button
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="robin_summary_{now}.md">Download Report</a></div>'
        st.markdown(href, unsafe_allow_html=True)
        
        status_slot.success("✔️ Investigation Complete")

    except Exception as e:
        st.error(f"An error occurred: {e}")
