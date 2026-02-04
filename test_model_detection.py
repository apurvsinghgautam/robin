#!/usr/bin/env python3
"""Test model detection logic."""

def is_ollama_model(model: str) -> bool:
    """Check if model is Ollama (not Claude)."""
    claude_prefixes = ["claude-", "claude_"]
    return not any(model.lower().startswith(prefix) for prefix in claude_prefixes)

# Test cases
test_cases = [
    ("claude-sonnet-4-20250514", False, "Claude"),
    ("claude-opus-4", False, "Claude"),
    ("llama3.1", True, "Ollama"),
    ("mistral", True, "Ollama"),
    ("deepseek-r1", True, "Ollama"),
]

print("Testing model detection:")
all_passed = True
for model, expected_ollama, expected_type in test_cases:
    result = is_ollama_model(model)
    status = "✓" if result == expected_ollama else "✗"
    result_type = "Ollama" if result else "Claude"
    print(f"{status} {model}: {result_type} (expected: {expected_type})")
    if result != expected_ollama:
        all_passed = False

if all_passed:
    print("\n✓ All model detection tests passed!")
else:
    print("\n✗ Some tests failed")
    exit(1)
