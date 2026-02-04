# Settings Page UI Enhancement - Model Selector

## New "AI Models" Section

The settings page now includes a new "AI Models" section at the top that displays:

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  🧠 AI Models                                    🔄 Refresh  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Current Model                            [CLAUDE]    │   │
│  │ claude-sonnet-4-20250514                             │   │
│  │ Set via ROBIN_MODEL environment variable             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Claude (Anthropic)              ✓  [Connected]       │   │
│  │ Available models:                                     │   │
│  │ [claude-sonnet-4-20250514*] [claude-opus-4]...       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Ollama (Local)                  ✗  [Not available]   │   │
│  │ Endpoint: http://127.0.0.1:11434                     │   │
│  │ Install and run Ollama to use local models           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Features

1. **Current Model Display**
   - Shows the active model name
   - Badge indicating type (CLAUDE or OLLAMA)
   - Note about environment variable configuration

2. **Claude (Anthropic) Section**
   - Green checkmark (✓) if API key is configured
   - Red X (✗) if not configured
   - Status badge: "Connected" or "Not configured"
   - List of available Claude models as chips
   - Current model is highlighted with blue border

3. **Ollama (Local) Section**
   - Green checkmark (✓) if Ollama is running and models found
   - Red X (✗) if not available
   - Status badge: "Connected" or "Not available"
   - Shows Ollama endpoint URL
   - Lists all available local models as chips
   - Current model is highlighted if it's an Ollama model
   - Help text with link to ollama.ai if not available

4. **Refresh Button**
   - Icon button in top-right corner
   - Spins during loading
   - Reloads model information from backend

### Color Scheme

- **Background**: Slate-900 (dark theme)
- **Borders**: Slate-800
- **Text**: 
  - Primary: Slate-100
  - Secondary: Slate-400
- **Status Indicators**:
  - Connected: Green-400 (✓)
  - Not Available: Red-400 (✗)
- **Badges**:
  - Connected: Green background
  - Not configured: Red background
  - Model type: Blue background
- **Model Chips**:
  - Default: Slate-700 background
  - Selected: Blue-500 background with border

### User Benefits

1. **At-a-glance status**: Immediately see which AI providers are configured and available
2. **Connection verification**: Confirms that Ollama is running and accessible
3. **Model discovery**: Shows all available models without needing to check documentation
4. **Current configuration**: Clearly displays which model is being used
5. **Troubleshooting**: Provides helpful information if providers aren't available
