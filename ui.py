import base64
import streamlit as st
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
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
    page_title="Jewel: AI-Powered Web Scraper",
    page_icon="💎",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown(
    """
    <style>
        body {
            background-color: #f8fafc;
            color: #0f172a;
        }
        .hero {
            background: linear-gradient(120deg, #e0f7ff, #f5ecff);
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 18px;
            border: 1px solid rgba(15, 23, 42, 0.05);
        }
        .hero h1 {
            margin-bottom: 0.25em;
            color: #4338ca;
        }
        .hero p {
            font-size: 1.05rem;
            margin-bottom: 0;
        }
        .hero-pills {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 16px;
        }
        .pill {
            background: rgba(67, 56, 202, 0.08);
            color: #4338ca;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.9rem;
            font-weight: 600;
        }
        .colHeight {
            max-height: 40vh;
            overflow-y: auto;
            text-align: center;
        }
        .pTitle {
            font-weight: bold;
            color: #4338ca;
            margin-bottom: 0.5em;
        }
        .aStyle {
            font-size: 18px;
            font-weight: bold;
            padding: 5px;
            padding-left: 0px;
            text-align: center;
        }
    </style>""",
    unsafe_allow_html=True,
)


# Sidebar
st.sidebar.title("Jewel")
st.sidebar.caption("AI-Powered Web Companion 💎")
st.sidebar.markdown(
    """Made by [Imani Ndolo](https://www.linkedin.com/in/imani-ndolo/)"""
)
st.sidebar.write(
    "Jewel walks through refine → search → filter → summarize so you can stay focused on insights."
)
st.sidebar.subheader("Settings")
model = st.sidebar.selectbox(
    "Choose an LLM model",
    [
        "gpt4o", "gpt-4.1", 
        "claude-3-5-sonnet-latest", 
        "llama3.1", 
        "gemini-2.5-flash",
        "gemini-flash-latest"
    ],
    key="model_select",
)
threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")
st.sidebar.info("Need inspo? Try “impact of AI on climate funding” or “top privacy startups 2025”.")


# Main UI - hero and input
st.markdown(
    """
    <div class="hero">
        <p class="pill" style="display:inline-block;margin-bottom:12px;">AI Powered Web Scraping</p>
        <h1>💎 Meet Jewel</h1>
        <p>Transform curiosities into confident research briefs with a calm, proven workflow.</p>
        <div class="hero-pills">
            <span class="pill">Refines your prompt</span>
            <span class="pill">Curates high-signal links</span>
            <span class="pill">Scrapes and summarizes kindly</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Display text box and button
with st.form("search_form", clear_on_submit=True):
    col_input, col_button = st.columns([10, 1])
    query = col_input.text_input(
        "What should Jewel look into?",
        placeholder="Ask anything you'd Google for deep research…",
        label_visibility="collapsed",
        key="query_input",
    )
    run_button = col_button.form_submit_button("Run")
st.caption("Tip: the more context you add (audience, format, timeframe), the better Jewel can help.")

# Display a status message
status_slot = st.empty()
# Pre-allocate three placeholders-one per card
cols = st.columns(3)
p1, p2, p3 = [col.empty() for col in cols]
# Friendly placeholder cards
default_cards = [
    ("Refined Query", "Jewel will tidy your question for precise searching."),
    ("Search Results", "We gather fresh links and data across the open web."),
    ("Filtered Results", "Low-signal sources get filtered so only quality remains."),
]
for placeholder, (title, text) in zip((p1, p2, p3), default_cards):
    placeholder.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>{title}</p><p>{text}</p></div>",
        unsafe_allow_html=True,
    )
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
            llm = get_llm(model)

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            st.session_state.refined = refine_query(llm, query)
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 3 - Search web
    with status_slot.container():
        with st.spinner("🔍 Searching web..."):
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("🗂️ Filtering results..."):
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results
            )
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("📜 Scraping content..."):
            st.session_state.scraped = cached_scrape_multiple(
                st.session_state.filtered, threads
            )

    # Stage 6 - Summarize
    # 6a) Prepare session state for streaming text
    st.session_state.streamed_summary = ""

    # 6c) UI callback for each chunk
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        summary_slot.markdown(st.session_state.streamed_summary)

    with summary_container_placeholder.container():  # border=True, height=450):
        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
        with hdr_col:
            st.subheader("💠 Investigation Summary", anchor=None, divider="gray")
        summary_slot = st.empty()

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("✍️ Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)

    with btn_col:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)
    status_slot.success("✔️ Pipeline completed successfully!")
