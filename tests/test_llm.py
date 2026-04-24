"""Tests for agent/llm.py — LLM client abstraction."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from agent.llm import ChatResponse, LLMClient, ToolCall, make_client


# ── Helpers ────────────────────────────────────────────────────────────────────

def _text_block(text: str) -> MagicMock:
    """Simulate an Anthropic text content block."""
    b = MagicMock(spec=["type", "text"])
    b.type = "text"
    b.text = text
    return b


def _tool_use_block(id: str, name: str, input: dict) -> MagicMock:
    """Simulate an Anthropic tool_use content block."""
    b = MagicMock(spec=["type", "id", "name", "input"])
    b.type = "tool_use"
    b.id = id
    b.name = name
    b.input = input
    return b


# ── LLMClient static helper ────────────────────────────────────────────────────

class TestUserMessage:
    def test_format(self):
        msg = LLMClient.user_message("hello")
        assert msg == {"role": "user", "content": "hello"}


# ── AnthropicClient ────────────────────────────────────────────────────────────

class TestAnthropicClient:
    def _make_client(self, model: str = "claude-opus-4-6"):
        """Instantiate AnthropicClient with a mocked anthropic module."""
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            from agent.llm import AnthropicClient
            client = AnthropicClient.__new__(AnthropicClient)
            client._client = mock_anthropic.Anthropic()
            client._model = model
        return client, mock_anthropic

    def test_send_text_only(self):
        client, mock_anthropic = self._make_client()
        text_block = _text_block("Hello!")
        mock_response = MagicMock()
        mock_response.content = [text_block]
        client._client.messages.create.return_value = mock_response

        result = client.send("sys", [], [])

        assert result.text == "Hello!"
        assert result.tool_calls == []

    def test_send_tool_use_only(self):
        client, _ = self._make_client()
        tc_block = _tool_use_block("tc1", "my_tool", {"x": 1})
        mock_response = MagicMock()
        mock_response.content = [tc_block]
        client._client.messages.create.return_value = mock_response

        result = client.send("sys", [], [])

        assert result.text is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "tc1"
        assert result.tool_calls[0].name == "my_tool"
        assert result.tool_calls[0].input == {"x": 1}

    def test_send_mixed_content(self):
        client, _ = self._make_client()
        mock_response = MagicMock()
        mock_response.content = [
            _text_block("thinking..."),
            _tool_use_block("tc2", "tool_b", {}),
        ]
        client._client.messages.create.return_value = mock_response

        result = client.send("sys", [], [])

        assert result.text == "thinking..."
        assert len(result.tool_calls) == 1

    def test_pack_assistant(self):
        client, _ = self._make_client()
        native_content = [_text_block("hi")]
        response = ChatResponse(text="hi", tool_calls=[], _native=native_content)
        packed = client.pack_assistant(response)
        assert packed == [{"role": "assistant", "content": native_content}]

    def test_pack_tool_results(self):
        client, _ = self._make_client()
        calls = [ToolCall(id="tc1", name="tool_a", input={})]
        results = ['{"ok": true}']
        packed = client.pack_tool_results(calls, results)
        assert packed == [{
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "tc1", "content": '{"ok": true}'}],
        }]

    def test_pack_tool_results_multiple(self):
        client, _ = self._make_client()
        calls = [
            ToolCall(id="a", name="tool_a", input={}),
            ToolCall(id="b", name="tool_b", input={}),
        ]
        results = ["result_a", "result_b"]
        packed = client.pack_tool_results(calls, results)
        content = packed[0]["content"]
        assert len(content) == 2
        assert content[0]["tool_use_id"] == "a"
        assert content[1]["tool_use_id"] == "b"

    def test_send_passes_model_and_tools(self):
        client, _ = self._make_client(model="claude-test-model")
        mock_response = MagicMock()
        mock_response.content = []
        client._client.messages.create.return_value = mock_response
        tools = [{"name": "my_tool", "input_schema": {}}]

        client.send("system prompt", [{"role": "user", "content": "hi"}], tools)

        call_kwargs = client._client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-test-model"
        assert call_kwargs["tools"] == tools
        assert call_kwargs["system"] == "system prompt"


# ── OpenAIClient ───────────────────────────────────────────────────────────────

class TestOpenAIClient:
    def _make_client(self, model: str = "gpt-4o"):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            from agent.llm import OpenAIClient
            client = OpenAIClient.__new__(OpenAIClient)
            client._client = mock_openai.OpenAI()
            client._model = model
        return client, mock_openai

    def _make_choice(self, content: str | None, tool_calls=None):
        msg = MagicMock()
        msg.content = content
        msg.tool_calls = tool_calls or []
        choice = MagicMock()
        choice.message = msg
        return choice

    def test_send_text_only(self):
        client, _ = self._make_client()
        mock_response = MagicMock()
        mock_response.choices = [self._make_choice("Hello from GPT")]
        client._client.chat.completions.create.return_value = mock_response

        result = client.send("sys", [], [])

        assert result.text == "Hello from GPT"
        assert result.tool_calls == []

    def test_send_with_tool_calls(self):
        client, _ = self._make_client()
        tc = MagicMock()
        tc.id = "call_1"
        tc.function.name = "my_tool"
        tc.function.arguments = json.dumps({"key": "val"})
        mock_response = MagicMock()
        mock_response.choices = [self._make_choice(None, tool_calls=[tc])]
        client._client.chat.completions.create.return_value = mock_response

        result = client.send("sys", [], [])

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "call_1"
        assert result.tool_calls[0].name == "my_tool"
        assert result.tool_calls[0].input == {"key": "val"}

    def test_to_openai_tools_conversion(self):
        from agent.llm import OpenAIClient
        anthropic_tools = [{
            "name": "my_tool",
            "description": "does things",
            "input_schema": {"type": "object", "properties": {}},
        }]
        result = OpenAIClient._to_openai_tools(anthropic_tools)
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "my_tool"
        assert result[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_pack_tool_results(self):
        client, _ = self._make_client()
        calls = [ToolCall(id="c1", name="tool_a", input={})]
        results = ["ok"]
        packed = client.pack_tool_results(calls, results)
        assert packed == [{"role": "tool", "tool_call_id": "c1", "content": "ok"}]

    def test_pack_tool_results_one_per_call(self):
        client, _ = self._make_client()
        calls = [
            ToolCall(id="x", name="t1", input={}),
            ToolCall(id="y", name="t2", input={}),
        ]
        packed = client.pack_tool_results(calls, ["r1", "r2"])
        assert len(packed) == 2
        assert packed[0]["tool_call_id"] == "x"
        assert packed[1]["tool_call_id"] == "y"

    def test_pack_assistant_without_tool_calls(self):
        client, _ = self._make_client()
        msg = MagicMock()
        msg.content = "hello"
        msg.tool_calls = None
        response = ChatResponse(text="hello", tool_calls=[], _native=msg)
        packed = client.pack_assistant(response)
        assert packed[0]["role"] == "assistant"
        assert packed[0]["content"] == "hello"
        assert "tool_calls" not in packed[0]

    def test_openai_import_error(self):
        with patch.dict("sys.modules", {"openai": None}):
            # Force re-import; remove cached version
            sys.modules.pop("agent.llm", None)
            from agent.llm import OpenAIClient
            with pytest.raises(ImportError, match="openai package"):
                OpenAIClient()


# ── make_client factory ────────────────────────────────────────────────────────

class TestMakeClient:
    def test_claude_returns_anthropic(self):
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            sys.modules.pop("agent.llm", None)
            from agent.llm import make_client, AnthropicClient
            client = make_client("claude")
            assert isinstance(client, AnthropicClient)

    def test_codex_returns_openai(self):
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            sys.modules.pop("agent.llm", None)
            from agent.llm import make_client, OpenAIClient
            client = make_client("codex")
            assert isinstance(client, OpenAIClient)

    def test_invalid_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            make_client("invalid")

    def test_model_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-override")
        mock_anthropic = MagicMock()
        with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
            sys.modules.pop("agent.llm", None)
            from agent.llm import make_client
            client = make_client("claude")
            assert client._model == "claude-test-override"
