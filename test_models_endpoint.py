#!/usr/bin/env python3
"""Test the models endpoint."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the necessary imports
os.environ['ANTHROPIC_API_KEY'] = 'test-key'
os.environ['OLLAMA_BASE_URL'] = 'http://127.0.0.1:11434'

try:
    from agent.ollama_client import get_available_ollama_models, is_ollama_model
    from config import DEFAULT_MODEL, ANTHROPIC_API_KEY, OLLAMA_BASE_URL
    
    print("✓ Successfully imported agent modules")
    print(f"  DEFAULT_MODEL: {DEFAULT_MODEL}")
    print(f"  ANTHROPIC_API_KEY: {'set' if ANTHROPIC_API_KEY else 'not set'}")
    print(f"  OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
    
    # Test model detection
    print("\n✓ Testing model detection:")
    test_models = [
        "claude-sonnet-4-20250514",
        "llama3.1",
        "mistral"
    ]
    for model in test_models:
        is_ollama = is_ollama_model(model)
        print(f"  {model}: {'Ollama' if is_ollama else 'Claude'}")
    
    # Try to get Ollama models (will fail if not running)
    print("\n✓ Checking Ollama availability:")
    try:
        ollama_models = get_available_ollama_models()
        if ollama_models:
            print(f"  Found {len(ollama_models)} Ollama model(s): {', '.join(ollama_models)}")
        else:
            print("  No Ollama models found (Ollama may not be running)")
    except Exception as e:
        print(f"  Cannot connect to Ollama: {e}")
    
    print("\n✓ All tests passed!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)
