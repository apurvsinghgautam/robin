"""
Antigravity OAuth Client for Robin

This module provides Google Pro subscription access via the Cloudcode/Antigravity API,
allowing users to use Gemini models without API keys.

Based on the MediBrief implementation and oh-my-opencode reference.
"""

import os
import json
import time
import logging
import webbrowser
from pathlib import Path
from typing import Optional, Generator, List, Dict, Any, Callable
from urllib.parse import urlencode

import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

logger = logging.getLogger(__name__)

# OAuth Configuration
SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/cclog',
    'https://www.googleapis.com/auth/experimentsandconfigs'
]

# Antigravity API Configuration
ANTIGRAVITY_ENDPOINTS = [
    'https://daily-cloudcode-pa.sandbox.googleapis.com',      # dev
    'https://autopush-cloudcode-pa.sandbox.googleapis.com',   # staging
    'https://cloudcode-pa.googleapis.com'                     # prod
]
ANTIGRAVITY_API_VERSION = 'v1internal'
ANTIGRAVITY_HEADERS = {
    'User-Agent': 'google-api-nodejs-client/9.15.1',
    'X-Goog-Api-Client': 'google-cloud-sdk vscode_cloudshelleditor/0.1',
}
ANTIGRAVITY_DEFAULT_PROJECT_ID = 'rising-fact-p41fc'

# Token cache location
TOKEN_CACHE_DIR = Path.home() / '.robin'
TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / 'token.json'


def get_client_config() -> Dict[str, Any]:
    """Build OAuth client config from environment variables."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError(
            "OAuth credentials not configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env file."
        )
    
    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/", "urn:ietf:wg:oauth:2.0:oob"]
        }
    }


def load_cached_credentials() -> Optional[Credentials]:
    """Load cached OAuth credentials from disk."""
    if not TOKEN_CACHE_FILE.exists():
        return None
    
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_CACHE_FILE), SCOPES)
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials(creds)
        
        return creds if creds and creds.valid else None
    except Exception as e:
        logger.warning(f"Failed to load cached credentials: {e}")
        return None


def save_credentials(creds: Credentials) -> None:
    """Save OAuth credentials to disk."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(TOKEN_CACHE_FILE, 'w') as f:
        f.write(creds.to_json())
    
    logger.info(f"Credentials saved to {TOKEN_CACHE_FILE}")


def clear_credentials() -> bool:
    """Clear cached OAuth credentials."""
    if TOKEN_CACHE_FILE.exists():
        TOKEN_CACHE_FILE.unlink()
        return True
    return False


def authenticate_cli() -> Credentials:
    """
    Run OAuth flow for CLI usage.
    Opens browser for authentication and caches tokens.
    """
    # Check for cached credentials first
    creds = load_cached_credentials()
    if creds:
        logger.info("Using cached credentials")
        return creds
    
    # Run OAuth flow
    client_config = get_client_config()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    print("\n🔐 Opening browser for Google authentication...")
    print("   If browser doesn't open, visit the URL printed below.\n")
    
    creds = flow.run_local_server(
        port=8080,
        prompt='consent',
        access_type='offline'
    )
    
    # Save for future use
    save_credentials(creds)
    
    # Get user info
    user_info = get_user_info(creds.token)
    if user_info:
        print(f"✅ Authenticated as: {user_info.get('email', 'Unknown')}")
    
    return creds


def generate_auth_url(redirect_uri: str = "http://localhost:8501") -> str:
    """
    Generate OAuth authorization URL for Streamlit UI flow.
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID not configured")
    
    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str = "http://localhost:8501") -> Dict[str, Any]:
    """
    Exchange authorization code for OAuth tokens (Streamlit UI flow).
    """
    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Token exchange failed: {response.text}")
    
    return response.json()


def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh access token using refresh token."""
    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"Token refresh failed: {response.text}")
    
    return response.json()


def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user info from Google."""
    try:
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Failed to get user info: {e}")
    return None


class AntigravityClient:
    """
    Client for the Cloudcode/Antigravity API.
    Handles project context and content generation.
    """
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.project_id: Optional[str] = None
        self._project_context_cached = False
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            **ANTIGRAVITY_HEADERS,
            'Client-Metadata': json.dumps({
                'ideType': 'IDE_UNSPECIFIED',
                'platform': 'PLATFORM_UNSPECIFIED',
                'pluginType': 'GEMINI'
            })
        }
    
    def load_project_context(self) -> str:
        """
        Call loadCodeAssist API to get project ID.
        Falls back to default project if API fails.
        """
        if self._project_context_cached and self.project_id:
            return self.project_id
        
        metadata = {
            'ideType': 'IDE_UNSPECIFIED',
            'platform': 'PLATFORM_UNSPECIFIED',
            'pluginType': 'GEMINI'
        }
        
        for endpoint in ANTIGRAVITY_ENDPOINTS:
            url = f"{endpoint}/{ANTIGRAVITY_API_VERSION}:loadCodeAssist"
            logger.info(f"Calling loadCodeAssist: {url}")
            
            try:
                response = requests.post(
                    url,
                    headers=self._get_headers(),
                    json={'metadata': metadata},
                    timeout=10
                )
                
                if not response.ok:
                    logger.warning(f"loadCodeAssist failed: {response.status_code}")
                    continue
                
                data = response.json()
                logger.info(f"loadCodeAssist response: {json.dumps(data, indent=2)}")
                
                # Extract project ID
                project_id = data.get('cloudaicompanionProject')
                if isinstance(project_id, dict):
                    project_id = project_id.get('id')
                
                if project_id:
                    self.project_id = project_id
                    self._project_context_cached = True
                    return project_id
                
                # Try onboarding if no project
                if data.get('allowedTiers'):
                    tier_id = data.get('currentTier', {}).get('id') or \
                              data.get('allowedTiers', [{}])[0].get('id') or 'free-tier'
                    
                    onboard_url = f"{endpoint}/{ANTIGRAVITY_API_VERSION}:onboardUser"
                    onboard_response = requests.post(
                        onboard_url,
                        headers=self._get_headers(),
                        json={'tierId': tier_id, 'metadata': metadata},
                        timeout=10
                    )
                    
                    if onboard_response.ok:
                        onboard_data = onboard_response.json()
                        managed_id = onboard_data.get('response', {}).get('cloudaicompanionProject', {}).get('id')
                        if onboard_data.get('done') and managed_id:
                            self.project_id = managed_id
                            self._project_context_cached = True
                            return managed_id
            
            except requests.RequestException as e:
                logger.warning(f"loadCodeAssist error: {e}")
                continue
        
        # Fallback to default project
        logger.warning(f"Using fallback project: {ANTIGRAVITY_DEFAULT_PROJECT_ID}")
        self.project_id = ANTIGRAVITY_DEFAULT_PROJECT_ID
        self._project_context_cached = True
        return self.project_id
    
    def generate_content_stream(
        self,
        contents: List[Dict[str, Any]],
        model: str = 'gemini-3-flash-preview',
        temperature: float = 0.7,
        system_instruction: Optional[str] = None
    ) -> Generator[str, None, None]:
        """
        Stream content generation from Antigravity API.
        Yields text chunks as they arrive.
        """
        import uuid
        
        project_id = self.load_project_context()
        request_id = f"robin-{uuid.uuid4()}"
        
        # Build request body
        body = {
            'project': project_id,
            'model': model,
            'userAgent': 'robin',
            'requestId': request_id,
            'request': {
                'contents': contents,
                'generationConfig': {
                    'temperature': temperature
                }
            }
        }
        
        if system_instruction:
            body['request']['systemInstruction'] = {
                'parts': [{'text': system_instruction}]
            }
        
        # Try endpoints in order
        GCP_PERMISSION_ERROR_PATTERNS = [
            'PERMISSION_DENIED',
            'does not have permission',
            'Cloud AI Companion API has not been used',
            'has not been enabled'
        ]
        
        for endpoint in ANTIGRAVITY_ENDPOINTS:
            api_url = f"{endpoint}/v1internal:streamGenerateContent?alt=sse"
            logger.info(f"Trying endpoint: {endpoint}")
            
            max_retries = 10
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        api_url,
                        headers={
                            **self._get_headers(),
                            'Accept': 'text/event-stream'
                        },
                        json=body,
                        stream=True,
                        timeout=60
                    )
                    
                    if response.ok:
                        logger.info(f"✅ Success with: {endpoint}")
                        
                        # Process SSE stream
                        for line in response.iter_lines(decode_unicode=True):
                            if line and line.startswith('data: '):
                                data = line[6:]
                                if data == '[DONE]':
                                    return
                                
                                try:
                                    parsed = json.loads(data)
                                    # Unwrap Antigravity response
                                    unwrapped = parsed.get('response', parsed)
                                    parts = unwrapped.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                                    
                                    for part in parts:
                                        if 'text' in part:
                                            yield part['text']
                                except json.JSONDecodeError:
                                    continue
                        return
                    
                    # Handle permission errors with retry
                    if response.status_code == 403:
                        error_text = response.text
                        if any(p in error_text for p in GCP_PERMISSION_ERROR_PATTERNS):
                            if attempt < max_retries - 1:
                                delay = min(200 * (2 ** attempt), 2000) / 1000
                                logger.info(f"GCP permission error, retry {attempt + 1}/{max_retries}")
                                time.sleep(delay)
                                continue
                    
                    logger.warning(f"Request failed: {response.status_code}")
                    break
                
                except requests.RequestException as e:
                    logger.error(f"Network error: {e}")
                    break
        
        raise Exception("All Antigravity endpoints failed")


class ChatAntigravity(BaseChatModel):
    """
    LangChain-compatible chat model using Antigravity API.
    
    This is a drop-in replacement for ChatGoogleGenerativeAI that uses
    OAuth authentication instead of API keys.
    """
    
    model: str = "gemini-3-flash-preview"
    temperature: float = 0.7
    streaming: bool = True
    access_token: Optional[str] = None
    _client: Optional[AntigravityClient] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Get access token from kwargs or cached credentials
        if not self.access_token:
            creds = load_cached_credentials()
            if creds:
                self.access_token = creds.token
            else:
                raise ValueError(
                    "No OAuth credentials available. "
                    "Run 'robin login' or login via UI first."
                )
        
        self._client = AntigravityClient(self.access_token)
    
    @property
    def _llm_type(self) -> str:
        return "antigravity"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature
        }
    
    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Convert LangChain messages to Antigravity format."""
        contents = []
        system_instruction = None
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # System messages become system instruction
                system_instruction = msg.content
            elif isinstance(msg, HumanMessage):
                contents.append({
                    'role': 'user',
                    'parts': [{'text': msg.content}]
                })
            elif isinstance(msg, AIMessage):
                contents.append({
                    'role': 'model',
                    'parts': [{'text': msg.content}]
                })
        
        return contents, system_instruction
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> ChatResult:
        """Generate a response from the model."""
        contents, system_instruction = self._convert_messages(messages)
        
        full_response = ""
        for chunk in self._client.generate_content_stream(
            contents=contents,
            model=self.model,
            temperature=self.temperature,
            system_instruction=system_instruction
        ):
            full_response += chunk
            if run_manager:
                run_manager.on_llm_new_token(chunk)
        
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=full_response))]
        )
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> Generator:
        """Stream response chunks from the model."""
        contents, system_instruction = self._convert_messages(messages)
        
        for chunk in self._client.generate_content_stream(
            contents=contents,
            model=self.model,
            temperature=self.temperature,
            system_instruction=system_instruction
        ):
            if run_manager:
                run_manager.on_llm_new_token(chunk)
            yield ChatGenerationChunk(message=AIMessageChunk(content=chunk))


def get_antigravity_token() -> Optional[str]:
    """Get the current cached access token, if any."""
    creds = load_cached_credentials()
    return creds.token if creds else None


def is_authenticated() -> bool:
    """Check if user is authenticated with valid credentials."""
    creds = load_cached_credentials()
    return creds is not None and creds.valid
