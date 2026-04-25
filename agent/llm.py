"""
LLM client abstraction for the agentic loop.

Supports Anthropic Claude and OpenAI (Codex / GPT) via a common interface.
Each adapter handles its own message-format details so main.py stays provider-agnostic.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class ChatResponse:
    text: str | None
    tool_calls: list[ToolCall]
    # Provider-specific raw response; used by pack_assistant / pack_tool_results.
    _native: Any = field(repr=False, compare=False)


class LLMClient(ABC):
    """Provider-agnostic interface for one turn of the agentic tool-use loop."""

    @abstractmethod
    def send(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> ChatResponse:
        """
        Make one LLM call and return a normalised response.
        tools must be in Anthropic input_schema format; adapters convert as needed.
        """

    @abstractmethod
    def pack_assistant(self, response: ChatResponse) -> list[dict]:
        """Convert a ChatResponse into the assistant-turn message(s) to append to history."""

    @abstractmethod
    def pack_tool_results(self, calls: list[ToolCall], results: list[str]) -> list[dict]:
        """Convert tool results into the tool-turn message(s) to append to history."""

    @staticmethod
    def user_message(text: str) -> dict:
        return {"role": "user", "content": text}


class AnthropicClient(LLMClient):
    """Claude via the Anthropic Messages API. Reads ANTHROPIC_API_KEY from env."""

    _DEFAULT_MODEL = "claude-opus-4-6"
    _ENV_VAR = "ANTHROPIC_MODEL"

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        import anthropic
        self._client = anthropic.Anthropic()
        self._model = model

    def send(self, system: str, messages: list[dict], tools: list[dict]) -> ChatResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8096,
            system=system,
            tools=tools,
            messages=messages,
        )
        text = next((b.text for b in response.content if hasattr(b, "text")), None)
        tool_calls = [
            ToolCall(id=b.id, name=b.name, input=b.input)
            for b in response.content
            if b.type == "tool_use"
        ]
        return ChatResponse(text=text, tool_calls=tool_calls, _native=response.content)

    def pack_assistant(self, response: ChatResponse) -> list[dict]:
        return [{"role": "assistant", "content": response._native}]

    def pack_tool_results(self, calls: list[ToolCall], results: list[str]) -> list[dict]:
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tc.id, "content": result}
            for tc, result in zip(calls, results)
        ]}]


class OpenAIClient(LLMClient):
    """
    OpenAI Chat Completions (Codex / GPT models). Reads OPENAI_API_KEY from env.
    Tool schemas are auto-converted from Anthropic input_schema format to OpenAI format.
    """

    _DEFAULT_MODEL = "gpt-4o"
    _ENV_VAR = "OPENAI_MODEL"

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai package is required for the OpenAI provider. "
                "Install it with: uv sync --extra openai"
            ) from exc
        self._client = openai.OpenAI()
        self._model = model

    @staticmethod
    def _to_openai_tools(tools: list[dict]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def send(self, system: str, messages: list[dict], tools: list[dict]) -> ChatResponse:
        all_messages = [{"role": "system", "content": system}, *messages]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,
            tools=self._to_openai_tools(tools),
            tool_choice="auto",
        )
        choice_msg = response.choices[0].message
        tool_calls: list[ToolCall] = []
        if choice_msg.tool_calls:
            for tc in choice_msg.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=json.loads(tc.function.arguments),
                ))
        return ChatResponse(text=choice_msg.content, tool_calls=tool_calls, _native=choice_msg)

    def pack_assistant(self, response: ChatResponse) -> list[dict]:
        msg = response._native
        out: dict[str, Any] = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            out["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        return [out]

    def pack_tool_results(self, calls: list[ToolCall], results: list[str]) -> list[dict]:
        # OpenAI expects one "tool" role message per result
        return [
            {"role": "tool", "tool_call_id": tc.id, "content": result}
            for tc, result in zip(calls, results)
        ]


# Registry maps provider name → client class. Add a new class + one entry here to extend.
_PROVIDERS: dict[str, type[LLMClient]] = {
    "claude": AnthropicClient,
    "codex": OpenAIClient,
}


def make_client(provider: str) -> LLMClient:
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. Choose from: {list(_PROVIDERS)}"
        )
    return cls(model=os.getenv(cls._ENV_VAR, cls._DEFAULT_MODEL))
