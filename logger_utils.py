"""
Logging utility for Robin OSINT Tool
Provides file logging and in-memory log storage for UI display
"""
import logging
import os
from datetime import datetime
from typing import List, Optional
from collections import deque

# Maximum number of log entries to keep in memory for UI display
MAX_LOG_ENTRIES = 1000

class RobinLogger:
    """Custom logger that writes to file and stores logs in memory for UI display"""
    
    def __init__(self, log_file: str = "robin.log"):
        self.log_file = log_file
        self.memory_logs = deque(maxlen=MAX_LOG_ENTRIES)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file) if os.path.dirname(log_file) else "."
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Setup file logger
        self.logger = logging.getLogger("robin")
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers = []
        
        # File handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler (optional, for debugging)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _add_to_memory(self, level: str, message: str):
        """Add log entry to in-memory storage"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.memory_logs.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
        self._add_to_memory('INFO', message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
        self._add_to_memory('WARNING', message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
        self._add_to_memory('ERROR', message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
        self._add_to_memory('DEBUG', message)
    
    def log_api_call(self, model: str, stage: str, prompt_type: str, data_preview: str, data_length: int):
        """Log API calls with data preview"""
        message = f"API Call - Model: {model} | Stage: {stage} | Type: {prompt_type} | Data Length: {data_length} chars"
        self.info(message)
        if data_preview:
            self.debug(f"Data Preview: {data_preview[:200]}...")
    
    def get_recent_logs(self, limit: int = 50) -> List[dict]:
        """Get recent log entries for UI display"""
        return list(self.memory_logs)[-limit:]
    
    def clear_logs(self):
        """Clear in-memory logs"""
        self.memory_logs.clear()
        self.info("Logs cleared")

# Global logger instance
_robin_logger: Optional[RobinLogger] = None

def get_logger() -> RobinLogger:
    """Get or create the global logger instance"""
    global _robin_logger
    if _robin_logger is None:
        _robin_logger = RobinLogger()
    return _robin_logger

def init_logger(log_file: str = "robin.log") -> RobinLogger:
    """Initialize the global logger with a custom log file"""
    global _robin_logger
    _robin_logger = RobinLogger(log_file)
    return _robin_logger

