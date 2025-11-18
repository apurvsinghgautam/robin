Title: Validate model API keys; add UX indicators and fail-fast behavior in CLI/UI

Summary
This PR improves user experience and reduces configuration errors by validating required API keys for the selected model. It provides clear messages in both CLI and Web UI and prevents runs that would fail due to missing configuration.

Changes
- llm.py
  - Added missing_model_env(model_choice) to determine which env vars are required per model.
  - get_llm() now validates required env vars and raises a friendly ValueError when missing.
- main.py (CLI)
  - Catches validation errors and prints a clear [ERROR] message instead of failing deep in the call stack.
- ui.py (Web UI)
  - Displays a sidebar indicator: "Model ready" or the list of missing variables.
  - Blocks pipeline start with a clear error if the model is missing required env vars.
- README.md
  - Documented "Model requirements" for each supported model.

Testing
- Manual
  - Unset OPENAI_API_KEY and try gpt-4.1: CLI shows error, UI shows warning and blocks run.
  - Set the key and verify normal operation.

Backward compatibility
- No breaking changes; only earlier validation and clearer messages.

Follow-ups
- In a future PR, surface per-provider rate-limit guidance and token usage tips; add a link to configuration docs.
