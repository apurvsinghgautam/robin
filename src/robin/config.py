import os
from pathlib import Path
import logging
from dotenv import load_dotenv

load_dotenv()


def get_project_root():
    """
    Get the project root directory by looking for pyproject.toml or other root markers.
    """
    current_path = Path(__file__).resolve()
    # Start from the current file's directory and go up until we find pyproject.toml
    for parent in current_path.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback: return the directory containing this file
    return current_path.parent

# Get the project root for better file path handling.
PROJECT_ROOT = get_project_root()

# Create logs directory if it doesn't exist
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Create logs directory if it doesn't exist
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Setup logging
def setup_logging():
    """Setup logging configuration."""
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create file handler
    log_file = LOGS_DIR / "robin.log"
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setFormatter(log_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Also add console handler for warnings and above in CLI mode
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    # In web UI mode, we'll set console handler to WARNING level to avoid cluttering terminal
    console_handler.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger(__name__)

# Configuration variables loaded from the .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
