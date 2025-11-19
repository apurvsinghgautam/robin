import base64
import re
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
            background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 25%, #16213e 50%, #0f1419 75%, #0a0a1a 100%);
            color: #e2e8f0;
        }
        .main .block-container {
            background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 25%, #16213e 50%, #0f1419 75%, #0a0a1a 100%);
        }
        .stContainer {
            background: linear-gradient(135deg, rgba(10, 10, 26, 0.95) 0%, rgba(26, 10, 46, 0.95) 25%, rgba(22, 33, 62, 0.95) 50%, rgba(15, 20, 25, 0.95) 75%, rgba(10, 10, 26, 0.95) 100%);
        }
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 25%, #16213e 50%, #0f1419 75%, #0a0a1a 100%);
        }
        .hero {
            background: linear-gradient(135deg, rgba(6, 78, 59, 0.15) 0%, rgba(30, 58, 138, 0.15) 50%, rgba(88, 28, 135, 0.15) 100%);
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 18px;
            border: 1px solid rgba(34, 211, 238, 0.3);
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(34, 211, 238, 0.2), 
                        0 0 60px rgba(88, 28, 135, 0.15),
                        inset 0 0 20px rgba(34, 211, 238, 0.1);
        }
        .hero h1 {
            margin-bottom: 0.25em;
            color: #7dd3fc;
            text-shadow: 0 0 10px rgba(125, 211, 252, 0.5), 0 0 20px rgba(125, 211, 252, 0.3);
        }
        .hero p {
            font-size: 1.05rem;
            margin-bottom: 0;
            color: #bae6fd;
        }
        .hero-pills {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 16px;
        }
        .pill {
            background: rgba(30, 58, 138, 0.25);
            color: #93c5fd;
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 1px solid rgba(34, 211, 238, 0.4);
            box-shadow: 0 0 10px rgba(34, 211, 238, 0.2), inset 0 0 5px rgba(34, 211, 238, 0.1);
        }
        .colHeight {
            max-height: 40vh;
            overflow-y: auto;
            text-align: center;
            background: linear-gradient(135deg, rgba(10, 10, 26, 0.9) 0%, rgba(22, 33, 62, 0.9) 50%, rgba(15, 20, 25, 0.9) 100%);
            border-radius: 12px;
            padding: 16px;
            color: #e2e8f0;
            border: 1px solid rgba(34, 211, 238, 0.2);
            box-shadow: 0 0 15px rgba(34, 211, 238, 0.15), inset 0 0 10px rgba(34, 211, 238, 0.05);
        }
        .pTitle {
            font-weight: bold;
            color: #60a5fa;
            margin-bottom: 0.5em;
            text-shadow: 0 0 8px rgba(96, 165, 250, 0.4);
        }
        .aStyle {
            font-size: 18px;
            font-weight: bold;
            padding: 5px;
            padding-left: 0px;
            text-align: center;
        }
        .aStyle a {
            color: #60a5fa;
            text-shadow: 0 0 5px rgba(96, 165, 250, 0.5);
        }
        .aStyle a:hover {
            color: #93c5fd;
            text-shadow: 0 0 10px rgba(147, 197, 253, 0.7);
        }
        /* Style for summary container */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] {
            background: linear-gradient(135deg, rgba(10, 10, 26, 0.95) 0%, rgba(22, 33, 62, 0.95) 50%, rgba(15, 20, 25, 0.95) 100%);
        }
        /* Make links in markdown clickable and styled */
        .stMarkdown a {
            color: #60a5fa;
            text-decoration: underline;
            text-shadow: 0 0 5px rgba(96, 165, 250, 0.4);
        }
        .stMarkdown a:hover {
            color: #93c5fd;
            text-shadow: 0 0 10px rgba(147, 197, 253, 0.6);
        }
        /* Style input boxes and form elements for dark theme */
        .stTextInput > div > div > input {
            background-color: rgba(10, 10, 26, 0.7);
            color: #e2e8f0;
            border: 1px solid rgba(34, 211, 238, 0.3);
            box-shadow: 0 0 10px rgba(34, 211, 238, 0.1), inset 0 0 5px rgba(34, 211, 238, 0.05);
        }
        .stTextInput > div > div > input:focus {
            border-color: #22d3ee;
            box-shadow: 0 0 15px rgba(34, 211, 238, 0.3), 
                        0 0 30px rgba(34, 211, 238, 0.2),
                        inset 0 0 10px rgba(34, 211, 238, 0.1);
        }
        /* Style buttons */
        .stButton > button {
            background: linear-gradient(135deg, rgba(30, 58, 138, 0.8) 0%, rgba(88, 28, 135, 0.8) 100%);
            color: #e0f2fe;
            border: 1px solid rgba(34, 211, 238, 0.5);
            box-shadow: 0 0 15px rgba(34, 211, 238, 0.3), inset 0 0 10px rgba(34, 211, 238, 0.1);
            text-shadow: 0 0 5px rgba(224, 242, 254, 0.5);
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, rgba(30, 58, 138, 1) 0%, rgba(88, 28, 135, 1) 100%);
            border-color: #22d3ee;
            box-shadow: 0 0 20px rgba(34, 211, 238, 0.5), 
                        0 0 40px rgba(34, 211, 238, 0.3),
                        inset 0 0 15px rgba(34, 211, 238, 0.2);
        }
        /* Style sidebar */
        [data-testid="stSidebar"] {
            background: linear-gradient(135deg, rgba(10, 10, 26, 0.95) 0%, rgba(26, 10, 46, 0.95) 25%, rgba(22, 33, 62, 0.95) 50%, rgba(15, 20, 25, 0.95) 75%, rgba(10, 10, 26, 0.95) 100%);
            box-shadow: 2px 0 20px rgba(34, 211, 238, 0.1);
        }
        /* Style containers with borders */
        [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
            background: linear-gradient(135deg, rgba(10, 10, 26, 0.85) 0%, rgba(22, 33, 62, 0.85) 50%, rgba(15, 20, 25, 0.85) 100%);
        }
        /* Add glow to section headers */
        h1, h2, h3 {
            text-shadow: 0 0 10px rgba(125, 211, 252, 0.3);
        }
        /* Glow effect for dividers */
        hr {
            border-color: rgba(34, 211, 238, 0.3);
            box-shadow: 0 0 5px rgba(34, 211, 238, 0.2);
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

    # Helper function to convert URLs to clickable markdown links
    def make_links_clickable(text: str) -> str:
        """Convert plain URLs in text to markdown links."""
        # Pattern to match URLs (http, https, www)
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+)'
        
        def replace_url(match):
            url = match.group(0)
            # Add protocol if it's a www link
            if url.startswith('www.'):
                full_url = 'https://' + url
            else:
                full_url = url
            # Truncate display text if too long
            display_text = url
            if len(display_text) > 60:
                display_text = display_text[:57] + '...'
            return f'[{display_text}]({full_url})'
        
        # Protect existing markdown links to avoid double-processing
        result = text
        markdown_links = []
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        
        # Find and temporarily replace existing markdown links
        for match in re.finditer(link_pattern, result):
            link_text = match.group(1)
            link_url = match.group(2)
            placeholder = f'__PROTECTED_LINK_{len(markdown_links)}__'
            markdown_links.append((link_text, link_url, placeholder))
            result = result.replace(match.group(0), placeholder, 1)
        
        # Replace remaining plain URLs with markdown links
        result = re.sub(url_pattern, replace_url, result)
        
        # Restore protected markdown links
        for link_text, link_url, placeholder in markdown_links:
            result = result.replace(placeholder, f'[{link_text}]({link_url})')
        
        return result

    with summary_container_placeholder.container():  # border=True, height=450):
        hdr_col, btn_col = st.columns([4, 1], vertical_alignment="center")
        with hdr_col:
            st.subheader("💠 Investigation Summary", anchor=None, divider="gray")
        summary_slot = st.empty()

    # 6c) UI callback for each chunk (defined after summary_slot is created)
    def ui_emit(chunk: str):
        st.session_state.streamed_summary += chunk
        # Convert URLs to clickable links before displaying
        clickable_summary = make_links_clickable(st.session_state.streamed_summary)
        summary_slot.markdown(clickable_summary)

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
