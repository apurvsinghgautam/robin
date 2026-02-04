# Using Robin with Ollama

Robin now supports both cloud-based Claude models and local Ollama models. This guide shows you how to use Ollama for privacy-focused, offline OSINT investigations.

## Why Use Ollama?

- **Privacy**: All processing happens locally, no data sent to external APIs
- **Cost**: Completely free, no API costs
- **Offline**: Works without internet (except for dark web access via Tor)
- **Control**: Full control over models and data

## Setup

### 1. Install Ollama

Visit https://ollama.ai and install Ollama for your platform:

```bash
# macOS/Linux
curl https://ollama.ai/install.sh | sh

# Or download from https://ollama.ai/download
```

### 2. Pull a Model

```bash
# Recommended models for OSINT work:
ollama pull llama3.1      # Good balance of speed and quality
ollama pull mistral       # Fast and efficient
ollama pull deepseek-r1   # Good for analysis
ollama pull llama3.2      # Latest version

# List available models
ollama list
```

### 3. Verify Ollama is Running

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Or
ollama ps
```

### 4. Configure Robin

Add to your `.env` file:

```bash
# Optional: Ollama URL (default is http://127.0.0.1:11434)
OLLAMA_BASE_URL=http://127.0.0.1:11434

# Set default model to Ollama
ROBIN_MODEL=llama3.1
```

## Usage Examples

### CLI Mode

```bash
# Basic investigation with Ollama
python main.py cli -q "ransomware payments 2024" -m llama3.1

# Interactive session
python main.py cli -q "threat actor APT28" -m mistral --interactive

# Save to file
python main.py cli -q "dark web markets" -m deepseek-r1 -o report.md
```

### Python API

```python
import asyncio
from agent import RobinAgent

async def investigate_with_ollama():
    agent = RobinAgent(
        model="llama3.1",  # Use Ollama model
        on_text=lambda t: print(t, end="", flush=True)
    )
    
    async for chunk in agent.investigate("ransomware payment methods"):
        pass  # Text printed by callback

asyncio.run(investigate_with_ollama())
```

### Check Available Models

```python
from agent import get_available_ollama_models

# Get list of installed Ollama models
models = get_available_ollama_models()
print("Available Ollama models:", models)
```

## Model Selection Guide

Different Ollama models work better for different tasks:

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| llama3.1 | 8B | Fast | High | General investigations |
| llama3.2 | 3B | Very Fast | Good | Quick queries |
| mistral | 7B | Fast | High | Technical analysis |
| deepseek-r1 | 8B | Medium | Very High | Deep analysis |
| qwen2.5 | 7B | Fast | High | Multilingual content |

```bash
# Pull specific model sizes
ollama pull llama3.1:8b      # 8 billion parameters
ollama pull llama3.1:70b     # 70 billion parameters (needs more RAM)
```

## Performance Tips

### 1. Hardware Requirements

- **Minimum**: 8GB RAM, 4GB free disk space
- **Recommended**: 16GB RAM, SSD storage
- **Optimal**: 32GB+ RAM, GPU support

### 2. Speed Optimization

```bash
# Use smaller models for faster responses
python main.py cli -q "quick check" -m llama3.2:3b

# Use larger models for better quality
python main.py cli -q "detailed analysis" -m llama3.1:70b
```

### 3. GPU Acceleration

If you have an NVIDIA GPU:

```bash
# Ollama automatically uses GPU if available
# Check GPU usage:
nvidia-smi

# Force CPU only (if needed):
CUDA_VISIBLE_DEVICES="" python main.py cli -q "query" -m llama3.1
```

## Limitations

When using Ollama instead of Claude:

1. **No Native Tool Calling**: Ollama models don't have native function calling like Claude. The agent uses a simplified approach where it provides direct analysis without autonomous tool usage.

2. **Single-Turn Analysis**: Ollama investigations currently use a single turn rather than the multi-turn agentic loop that Claude uses.

3. **Limited Context**: Ollama models have smaller context windows than Claude (8K-32K vs 200K tokens).

4. **No Sub-Agents**: The specialized sub-agents (ThreatActorProfiler, IOCExtractor, etc.) work best with Claude's structured outputs.

## Hybrid Approach

You can use both Claude and Ollama in the same project:

```python
# Use Claude for complex investigations
result1 = await run_investigation(
    "detailed APT analysis",
    model="claude-sonnet-4-20250514"
)

# Use Ollama for quick lookups
result2 = await run_investigation(
    "check dark web market status",
    model="llama3.1"
)
```

## Troubleshooting

### Ollama Not Connecting

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve

# Check logs
ollama logs
```

### Model Not Found

```bash
# List installed models
ollama list

# Pull the model if missing
ollama pull llama3.1
```

### Out of Memory

```bash
# Use a smaller model
python main.py cli -q "query" -m llama3.2:3b

# Or clear Ollama cache
ollama rm <model_name>
ollama pull <model_name>
```

### Slow Performance

- Use smaller models (3B-7B parameters)
- Close other applications
- Ensure you have adequate RAM
- Consider using GPU if available

## Best Practices

1. **Start Small**: Begin with llama3.1 or mistral for testing
2. **Monitor Resources**: Keep an eye on RAM and CPU usage
3. **Cache Models**: Keep frequently used models installed
4. **Regular Updates**: Update Ollama and models periodically

```bash
# Update Ollama
curl https://ollama.ai/install.sh | sh

# Update models
ollama pull llama3.1
```

## Privacy Considerations

When using Ollama:

- ✅ All LLM processing happens locally
- ✅ No data sent to external APIs for LLM inference
- ⚠️ Still requires Tor for dark web access
- ⚠️ Search queries still go through Tor to .onion sites
- ⚠️ Scraped content from dark web passes through your system

Ollama provides privacy for the AI analysis portion, but dark web access still requires proper operational security.

## Support

- Ollama Documentation: https://github.com/ollama/ollama
- Robin Issues: https://github.com/Squiblydoo/robin/issues
- Model Library: https://ollama.ai/library

---

**Note**: Ollama support in Robin is designed to be a drop-in replacement for the LLM layer. The architecture, tools, and dark web search capabilities remain the same regardless of which LLM backend you choose.
