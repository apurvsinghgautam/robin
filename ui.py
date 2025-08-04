import base64
import streamlit as st
from datetime import datetime
from scrape import scrape_multiple
from search import get_search_results
from llm_utils import BufferedStreamingHandler
from llm import get_llm, refine_query, filter_results, generate_summary
from langchain_ollama import ChatOllama
import requests
import json

# Cache expensive backend calls
@st.cache_data(ttl=200, show_spinner=False)
def cached_search_results(refined_query: str, threads: int):
    return get_search_results(refined_query.replace(" ", "+"), max_workers=threads)


@st.cache_data(ttl=200, show_spinner=False)
def cached_scrape_multiple(filtered: list, threads: int):
    return scrape_multiple(filtered, max_workers=threads)


def test_custom_connection(endpoint, endpoint_type, api_key, model=None):
    """Test connection to custom endpoint"""
    try:
        if endpoint_type == "ollama":
            # For Ollama, test the /api/tags endpoint
            response = requests.get(f"{endpoint}/api/tags", timeout=10)
            if response.status_code == 200:
                st.success("Ollama connection successful!")
                return True
            else:
                st.error(f" Ollama connection failed: {response.status_code}")
                return False
        elif endpoint_type == "openai":
            # For OpenAI, test with a simple API call
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(f"{endpoint}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                st.success("OpenAI connection successful!")
                return True
            else:
                st.error(f"OpenAI connection failed: {response.status_code}")
                return False
        else:
            st.error("Unsupported endpoint type")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Connection failed: Could not connect to endpoint")
        return False
    except requests.exceptions.Timeout:
        st.error("Connection failed: Request timed out")
        return False
    except Exception as e:
        st.error(f"Connection failed: {str(e)}")
        return False


def get_custom_llm_models(endpoint, endpoint_type, api_key):
    """Get available models from custom endpoint"""
    try:
        if endpoint_type == "ollama":
            # For Ollama, get models from /api/tags
            response = requests.get(f"{endpoint}/api/tags", timeout=10)
            if response.status_code == 200:
                models_data = response.json()
                models = [model['name'] for model in models_data.get('models', [])]
                return models if models else ["llama3.1", "mistral", "codellama", "llama2", "llama2:13b", "llama2:70b", "mistral:7b", "mistral:13b", "codellama:7b", "codellama:13b", "codellama:34b"]
            else:
                st.warning(f"Could not fetch Ollama models: {response.status_code}")
                return ["llama3.1", "mistral", "codellama", "llama2", "llama2:13b", "llama2:70b", "mistral:7b", "mistral:13b", "codellama:7b", "codellama:13b", "codellama:34b"]
        elif endpoint_type == "openai":
            # For OpenAI, get models from /models endpoint
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            response = requests.get(f"{endpoint}/models", headers=headers, timeout=10)
            if response.status_code == 200:
                models_data = response.json()
                models = [model['id'] for model in models_data.get('data', [])]
                return models if models else ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
            else:
                st.warning(f"Could not fetch OpenAI models: {response.status_code}")
                return ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        else:
            return ["gpt-4o", "llama3.1"]
    except Exception as e:
        st.warning(f"Error fetching models: {str(e)}")
        if endpoint_type == "ollama":
            return ["llama3.1", "mistral", "codellama", "llama2", "llama2:13b", "llama2:70b", "mistral:7b", "mistral:13b", "codellama:7b", "codellama:13b", "codellama:34b"]
        elif endpoint_type == "openai":
            return ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        else:
            return ["gpt-4o", "llama3.1"]


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
model = st.sidebar.selectbox(
    "Select LLM Model",
    ["gpt4o", "gpt-4.1", "claude-3-5-sonnet-latest", "llama3.1", "gemini-2.5-flash", "Custom"],
    key="model_select",
)

if model == "Custom":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Custom Endpoint Settings")
    
    
    
    # Endpoint configuration
    custom_endpoint = st.sidebar.text_input(
        "Endpoint URL", 
        value="http://localhost:11434", 
        help="For Ollama: http://localhost:11434"
    )
    
    custom_endpoint_type = st.sidebar.selectbox(
        "Endpoint Type", 
        ["ollama", "openai"],
        help="Select the type of endpoint you're connecting to"
    )
    
    # API Key (only for OpenAI)
    custom_api_key = None
    if custom_endpoint_type == "openai":
        custom_api_key = st.sidebar.text_input(
            "API Key", 
            type="password",
            help="Your OpenAI API key"
        )
    
    # Test connection and refresh buttons
    col1, col2 = st.sidebar.columns([1, 1])
    with col1:
        test_button = st.button("Test Connection", use_container_width=True)
    with col2:
        refresh_button = st.button("Refresh Models", use_container_width=True)
    
    # Get available models
    custom_endpoint_model_list = []
    if custom_endpoint and (refresh_button or not hasattr(st.session_state, 'custom_models_cached')):
        try:
            custom_endpoint_model_list = get_custom_llm_models(custom_endpoint, custom_endpoint_type, custom_api_key)
            st.session_state.custom_models_cached = custom_endpoint_model_list
            if refresh_button:
                st.sidebar.success("Models refreshed!")
        except Exception as e:
            st.sidebar.warning(f"Could not fetch models: {str(e)}")
            if custom_endpoint_type == "ollama":
                custom_endpoint_model_list = ["llama3.1", "mistral", "codellama", "llama2", "llama2:13b", "llama2:70b", "mistral:7b", "mistral:13b", "codellama:7b", "codellama:13b", "codellama:34b"]
            else:
                custom_endpoint_model_list = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
            st.session_state.custom_models_cached = custom_endpoint_model_list
    elif hasattr(st.session_state, 'custom_models_cached'):
        custom_endpoint_model_list = st.session_state.custom_models_cached
    
    # Model selection
    if custom_endpoint_model_list:
        custom_endpoint_model = st.sidebar.selectbox(
            "Select Model",
            custom_endpoint_model_list,
            help="Choose a model from your endpoint"
        )
    else:
        custom_endpoint_model = st.sidebar.text_input(
            "Model Name",
            value="llama3.1" if custom_endpoint_type == "ollama" else "gpt-4o",
            help="Enter the model name manually"
        )
    
    # Test connection
    if test_button:
        with st.sidebar:
            with st.spinner("Testing connection..."):
                test_custom_connection(custom_endpoint, custom_endpoint_type, custom_api_key)
    
    # Store custom endpoint info in session state for later use
    st.session_state.custom_endpoint = custom_endpoint
    st.session_state.custom_api_key = custom_api_key
    st.session_state.custom_endpoint_type = custom_endpoint_type
    st.session_state.custom_model = custom_endpoint_model

threads = st.sidebar.slider("Scraping Threads", 1, 16, 4, key="thread_slider")


# Main UI - logo and input
_, logo_col, _ = st.columns(3)
with logo_col:
    try:
        st.image(".github/assets/robin_logo.png", width=200)
    except:
        st.title("🕵️‍♂️ Robin")
        st.markdown("*AI-Powered Dark Web OSINT Tool*")

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
            # Check if we're using a custom endpoint
            if model == "Custom" and hasattr(st.session_state, 'custom_endpoint'):
                llm = get_llm(
                    st.session_state.custom_model, 
                    st.session_state.custom_endpoint, 
                    st.session_state.custom_api_key, 
                    st.session_state.custom_endpoint_type
                )
            else:
                llm = get_llm(model)

    # Stage 2 - Refine query
    with status_slot.container():
        with st.spinner("🔄 Refining query..."):
            st.session_state.refined = refine_query(llm, query)
    p1.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Refined Query</p><p>{st.session_state.refined}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 3 - Search dark web
    with status_slot.container():
        with st.spinner("🔍 Searching dark web..."):
            st.session_state.results = cached_search_results(
                st.session_state.refined, threads
            )
    p2.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Search Results</p><p>{len(st.session_state.results)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 4 - Filter results
    with status_slot.container():
        with st.spinner("Filtering results..."):
            st.session_state.filtered = filter_results(
                llm, st.session_state.refined, st.session_state.results
            )
    p3.container(border=True).markdown(
        f"<div class='colHeight'><p class='pTitle'>Filtered Results</p><p>{len(st.session_state.filtered)}</p></div>",
        unsafe_allow_html=True,
    )

    # Stage 5 - Scrape content
    with status_slot.container():
        with st.spinner("Scraping content..."):
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
            st.subheader(":red[Investigation Summary]", anchor=None, divider="gray")
        summary_slot = st.empty()

    # 6d) Inject your two callbacks and invoke exactly as before
    with status_slot.container():
        with st.spinner("Generating summary..."):
            stream_handler = BufferedStreamingHandler(ui_callback=ui_emit)
            llm.callbacks = [stream_handler]
            _ = generate_summary(llm, query, st.session_state.scraped)

    with btn_col:
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = f"summary_{now}.md"
        b64 = base64.b64encode(st.session_state.streamed_summary.encode()).decode()
        href = f'<div class="aStyle">📥 <a href="data:file/markdown;base64,{b64}" download="{fname}">Download</a></div>'
        st.markdown(href, unsafe_allow_html=True)
    status_slot.success("Pipeline completed successfully!")
