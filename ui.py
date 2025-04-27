"""
Streamlit UI for Robin: AI-Powered Dark Web OSINT Tool

Usage:
  # Run directly with Streamlit:
  streamlit run streamlit_app.py

Packaging as a standalone binary:
  pip install pyinstaller
  pyinstaller --onefile streamlit_app.py
  # Then run:
  dist/streamlit_app

This script wraps the Robin CLI functions (search, scrape, LLM) into a web interface.
"""

import streamlit as st
import time
from search import get_search_results
from scrape import scrape_multiple
from llm_utils import BufferedStreamingHandler
from llm import get_llm, refine_query, filter_results, generate_summary

# Streamlit page configuration 
st.set_page_config(
    page_title="Robin: AI-Powered Dark Web OSINT Tool",
    page_icon="🕵️‍♂️",
    # layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
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
    </style>""", unsafe_allow_html=True)


# Sidebar
st.sidebar.title("Robin")
st.sidebar.text("AI-Powered Dark Web OSINT Tool")
st.sidebar.markdown("""Made by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/), while on the 🕵️‍♂️""")
st.sidebar.subheader("Settings")
model = st.sidebar.selectbox(
    "Select LLM Model",
    ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash"],
)
threads = st.sidebar.slider("Scraping Threads", 1, 16, 4)


# Main UI
# Display logo
_, col, _ = st.columns(3)
with col:
    st.image("./assets/robin_logo.png", width=200)   

# Display text box and button
with st.form("search_form", clear_on_submit=True):
    col_input, col_button = st.columns([10, 1])
    query  = col_input.text_input("Enter Dark Web Search Query", placeholder="Enter Dark Web Search Query", label_visibility="collapsed", key="query")
    run_button = col_button.form_submit_button("Run")

# Process the query
if run_button and query:
    # Display a status message
    status_slot = st.empty()  
    # Pre-allocate three placeholders-one per card
    cols = st.columns(3)
    p1, p2, p3 = [col.empty() for col in cols]
    
    # Stage 1 - Load LLM
    with status_slot.container():
        with st.spinner("🔄 Loading LLM..."):
            llm = get_llm(model)

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            refined = refine_query(llm, query)
    p1.container(border=True).markdown(f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{refined}</p></div>", unsafe_allow_html=True)

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            results = get_search_results(refined.replace(' ', '+'), max_workers=threads)
    p2.container(border=True).markdown(f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(results)}</p></div>", unsafe_allow_html=True)

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            filtered = filter_results(llm, refined, results)
    p3.container(border=True).markdown(f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(filtered)}</p></div>", unsafe_allow_html=True)

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            scraped = scrape_multiple(filtered, max_workers=threads)

    # Stage 6 - Summarize
    # 6a) Prepare session state for streaming text
    if "streamed_summary" not in st.session_state:
            st.session_state.streamed_summary = ""
            
    # 6b) Wrap the summary in its own bordered container
    summary_container = st.container(border=True, height=300)
    with summary_container:
        hdr_col, btn_col = st.columns([4, 1])
        with hdr_col:
            st.subheader("Investigation Summary", anchor=None)
        with btn_col:
            # safe file name from the refined query
            safe_name = refined.replace(" ", "_")
            fname = f"investigation_summary_{safe_name}.md"
            st.download_button(
                label="📥 Download",
                data=st.session_state.streamed_summary,
                file_name=fname,
                mime="text/markdown",
                help="Download the summary as a markdown file.",
            )
        summary_slot = st.empty()

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, scraped)
    status_slot.success("✔️ Pipeline completed successfully!")
