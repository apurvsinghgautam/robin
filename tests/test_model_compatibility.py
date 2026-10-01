"""Real client serialization, with synthetic credentials and HTTP transports."""
import json
import unittest
from unittest import mock

import httpx
import httpx2
from google import genai
from langchain_anthropic import chat_models as anthropic_models
from langchain_core.messages import AIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

import health
import llm
import llm_utils
from config import RobinConfig


CFG = RobinConfig(openai_api_key="test-openai", anthropic_api_key="test-anthropic",
                  google_api_key="test-google", mistral_api_key="test-mistral",
                  openrouter_api_key="test-openrouter", ollama_base_url=None)
SAMPLING = {"temperature", "top_p", "top_k"}


def build(provider, model, **extra):
    config = llm_utils._provider_constructor(provider, model, CFG)
    config["constructor_params"].update(streaming=False, **extra)
    with mock.patch.object(llm, "resolve_model_config", return_value=config):
        return llm.get_llm(model, CFG)


class ClientRequests(unittest.TestCase):
    """Observe serialized HTTP bodies, not just arguments passed to LangChain."""

    def transport(self, response, http_module=httpx):
        bodies = []

        def send(request):
            bodies.append(json.loads(request.content))
            return http_module.Response(200, json=response)

        return http_module.MockTransport(send), bodies

    def chat_response(self, model):
        return {"id": "chatcmpl-test", "object": "chat.completion", "created": 0,
                "model": model, "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "OK"}}]}

    def test_openai_and_gateway_requests_omit_sampling(self):
        cases = [("openai", "gpt-4.1-mini"), ("openai", "gpt-5-mini"),
                 ("openai", "gpt-6-astra"), ("openai", "o3"), ("openai", "o1"),
                 ("openrouter", "anthropic/claude-sonnet-5.5"),
                 ("openrouter", "google/gemini-3.8-flash"),
                 ("openrouter", "deepseek/deepseek-r1")]
        for provider, model in cases:
            with self.subTest(provider=provider, model=model):
                transport, bodies = self.transport(self.chat_response(model), httpx2)
                with httpx2.Client(transport=transport) as http:
                    client = build(provider, model, http_client=http)
                    self.assertEqual(llm_utils.response_text(client.invoke("Say OK")), "OK")
                self.assertEqual(len(bodies), 1)
                self.assertFalse(SAMPLING & bodies[0].keys(), bodies[0])

    def test_claude_requests_omit_sampling(self):
        for model in ("claude-haiku-4-5", "claude-opus-4-7", "claude-sonnet-5-5"):
            with self.subTest(model=model):
                reply = {"id": "msg-test", "type": "message", "role": "assistant",
                         "model": model, "content": [{"type": "text", "text": "OK"}],
                         "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}}
                transport, bodies = self.transport(reply, httpx2)
                with httpx2.Client(transport=transport) as http, mock.patch.object(
                        anthropic_models, "_get_default_httpx_client", return_value=http):
                    self.assertEqual(llm_utils.response_text(build("anthropic", model).invoke("Say OK")), "OK")
                self.assertEqual(len(bodies), 1)
                self.assertFalse(SAMPLING & bodies[0].keys(), bodies[0])

    def test_gemini_requests_omit_sampling_for_current_models(self):
        for model in ("gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3.8-flash"):
            with self.subTest(model=model):
                reply = {"candidates": [{"content": {"role": "model", "parts": [{"text": "OK"}]},
                                         "finishReason": "STOP"}]}
                transport, bodies = self.transport(reply)
                with httpx.Client(transport=transport) as http:
                    google = genai.Client(api_key="test-google", http_options={"httpx_client": http})
                    client = build("google", model)
                    client.client = google
                    self.assertEqual(llm_utils.response_text(client.invoke("Say OK")), "OK")
                self.assertEqual(len(bodies), 1)
                self.assertFalse(SAMPLING & bodies[0].get("generationConfig", {}).keys(), bodies[0])

    def test_mistral_retains_the_clients_documented_sampling_default(self):
        transport, bodies = self.transport(self.chat_response("mistral-small-latest"))
        with httpx.Client(transport=transport, base_url="https://mistral.test/v1") as http:
            self.assertEqual(llm_utils.response_text(
                build("mistral", "mistral-small-latest", client=http).invoke("Say OK")), "OK")
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0]["temperature"], 0.7)

    def test_local_and_custom_requests_preserve_server_defaults(self):
        cases = [("llama", "qwen3", RobinConfig(llama_cpp_base_url="http://local.test")),
                 ("custom", "gpt-6-astra", RobinConfig(custom_api_base_url="http://custom.test",
                                                      custom_api_model="gpt-6-astra", ollama_base_url=None)),
                 ("ollama", "qwen3:4b", RobinConfig(ollama_base_url="http://ollama.test", ollama_num_ctx=16384))]
        for provider, model, cfg in cases:
            with self.subTest(provider=provider):
                reply = ({"model": model, "message": {"role": "assistant", "content": "OK"},
                          "done": True, "done_reason": "stop"} if provider == "ollama"
                         else self.chat_response(model))
                http_module = httpx if provider == "ollama" else httpx2
                transport, bodies = self.transport(reply, http_module)
                with http_module.Client(transport=transport) as http, \
                        mock.patch.object(llm_utils, "_registry_entries", return_value=[]), \
                        mock.patch.object(llm_utils, "fetch_llama_cpp_models", return_value=[model] if provider == "llama" else []), \
                        mock.patch.object(llm_utils, "fetch_custom_api_models", return_value=[]), \
                        mock.patch.object(llm_utils, "fetch_ollama_models", return_value=[model] if provider == "ollama" else []):
                    config = llm_utils.resolve_model_config(model, cfg)
                    self.assertFalse(SAMPLING & config["constructor_params"].keys())
                    if provider == "ollama":
                        config["constructor_params"]["sync_client_kwargs"] = {"transport": transport}
                    else:
                        config["constructor_params"]["http_client"] = http
                    with mock.patch.object(llm, "resolve_model_config", return_value=config):
                        client = llm.get_llm(model, cfg)
                    self.assertEqual(llm_utils.response_text(client.invoke("Say OK", stream=False)), "OK")
                self.assertEqual(len(bodies), 1)
                self.assertFalse(SAMPLING & bodies[0].keys(), bodies[0])
                if provider == "ollama":
                    self.assertFalse(SAMPLING & bodies[0]["options"].keys())
                    self.assertEqual(bodies[0]["options"]["num_ctx"], 16384)


class AnswerText(unittest.TestCase):
    """Reasoning, tool calls and truncated thoughts must never become an answer."""

    def test_modern_content_blocks_and_local_thinking_prefixes(self):
        cases = [(AIMessage(content="OK"), "OK"),
                 (AIMessage(content=[{"type": "thinking", "thinking": "Index 1 looks good"},
                                     {"type": "text", "text": "2, 4"}]), "2, 4"),
                 (AIMessage(content=[{"type": "reasoning", "summary": [{"text": "1, 3"}]},
                                     {"type": "text", "text": "2"}, " , 4"]), "2 , 4"),
                 ("<think>Consider 1, 3 and 2026.</think>\n2, 4", "2, 4"),
                 ("<think>first</think><thinking>second</thinking>OK", "OK"),
                 ("<think>Only a thought", ""),
                 (AIMessage(content=[{"type": "thinking", "thinking": "Only reasoning"}]), ""),
                 (AIMessage(content=[{"type": "tool_use", "name": "example", "text": "not an answer"}]), ""),
                 ("A quoted <think>example</think> stays intact.", "A quoted <think>example</think> stays intact.")]
        for response, expected in cases:
            with self.subTest(response=response):
                self.assertEqual(llm_utils.response_text(response), expected)

    def test_health_checks_accept_answer_blocks_but_reject_reasoning_only(self):
        for content, status in (([{"type": "text", "text": "OK"}], "up"),
                                ([{"type": "thinking", "thinking": "Thinking"}], "down"),
                                ("<think>Thinking</think>OK", "up")):
            with self.subTest(content=content), \
                    mock.patch.object(health, "resolve_model_config", return_value={
                        "class": llm_utils.ChatAnthropic, "constructor_params": {}}), \
                    mock.patch.object(health, "get_llm", return_value=mock.Mock(
                        **{"invoke.return_value": AIMessage(content=content)})):
                result = health.check_llm_health("claude-sonnet-5-5", CFG)
                self.assertEqual(result["status"], status)
                self.assertEqual(result["error"], None if status == "up" else "Empty response from API")

    def test_streams_exclude_reasoning_even_when_tags_span_tokens(self):
        for chunks, expected in ((("<thi", "nk>Index 1\n", "is plausible</th", "ink>", "2, 4"), "2, 4"),
                                 (("<think>" + "x" * 10000, "</think>OK"), "OK"),
                                 (("<think>unfinished" ,), ""),
                                 (("ordinary ", "<think>quoted</think> text"), "ordinary <think>quoted</think> text")):
            with self.subTest(chunks=chunks):
                seen = []
                handler = llm_utils.BufferedStreamingHandler(buffer_limit=1, ui_callback=seen.append)
                for token in chunks:
                    handler.on_llm_new_token(token)
                handler.on_llm_end(None)
                self.assertEqual("".join(seen), expected)
        seen = []
        handler = llm_utils.BufferedStreamingHandler(ui_callback=seen.append)
        reasoning = ChatGenerationChunk(message=AIMessageChunk(content=[{
            "type": "thinking", "thinking": "Index 1"}]))
        handler.on_llm_new_token("Index 1", chunk=reasoning)
        handler.on_llm_new_token("OK")
        handler.on_llm_end(None)
        self.assertEqual("".join(seen), "OK")

        seen.clear()
        for token in ("<think>", "Index 1", "</think>", "OK"):
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=[{"type": "text", "text": token}]))
            handler.on_llm_new_token(token, chunk=chunk)
        handler.on_llm_end(None)
        self.assertEqual("".join(seen), "OK")

        seen.clear()
        handler.on_llm_new_token("<think>interrupted")
        handler.on_llm_error(RuntimeError("provider interrupted the stream"))
        handler.on_llm_new_token("new answer")
        handler.on_llm_end(None)
        self.assertEqual("".join(seen), "new answer")


if __name__ == "__main__":
    unittest.main()
