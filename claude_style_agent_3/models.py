from __future__ import annotations

import json
import os
import re
import time
from typing import List, Optional

from openai import OpenAI

from agent_types import AgentDecision, Message, ToolCall


def _try_parse_tool_json(raw: str) -> AgentDecision | None:
    """Try to parse a TOOL JSON string, with fallback for malformed JSON."""
    raw = raw.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()

    # First try direct parse
    try:
        data = json.loads(raw)
        return AgentDecision(
            kind="tool",
            tool_call=ToolCall(
                tool_name=data["tool_name"],
                arguments=data.get("arguments", {}),
            ),
        )
    except json.JSONDecodeError:
        pass

    # Fallback: extract tool_name and arguments via regex
    name_match = re.search(r'"tool_name"\s*:\s*"([^"]+)"', raw)
    if not name_match:
        return None

    tool_name = name_match.group(1)
    args = {}

    # Try to extract the arguments object
    args_match = re.search(r'"arguments"\s*:\s*\{(.+)\}\s*\}', raw, re.DOTALL)
    if args_match:
        args_body = args_match.group(1)
        # Parse individual key-value pairs (handles simple string values)
        for kv in re.finditer(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"|"(\w+)"\s*:\s*([^,}\s]+)', args_body):
            if kv.group(1):
                args[kv.group(1)] = kv.group(2)
            elif kv.group(3):
                val = kv.group(4)
                # Try to parse as int/float/bool/null
                if val == "null":
                    args[kv.group(3)] = None
                elif val in ("true", "false"):
                    args[kv.group(3)] = val == "true"
                else:
                    try:
                        args[kv.group(3)] = int(val)
                    except ValueError:
                        try:
                            args[kv.group(3)] = float(val)
                        except ValueError:
                            args[kv.group(3)] = val

    return AgentDecision(
        kind="tool",
        tool_call=ToolCall(tool_name=tool_name, arguments=args),
    )


def parse_agent_response(text: str) -> AgentDecision:
    text = text.strip()

    # Helper: try to parse TOOL JSON from a raw string
    def _try_tool(raw: str) -> AgentDecision | None:
        return _try_parse_tool_json(raw)

    if text.startswith("TOOL:"):
        result = _try_tool(text[len("TOOL:"):])
        if result:
            return result

    if text.startswith("FINAL:"):
        return AgentDecision(
            kind="final",
            final_answer=text[len("FINAL:"):].strip(),
        )

    # Fallback: model may have prepended explanation before TOOL:/FINAL:
    tool_idx = text.find("\nTOOL:")
    if tool_idx != -1:
        result = _try_tool(text[tool_idx + len("\nTOOL:"):])
        if result:
            return result

    final_idx = text.find("\nFINAL:")
    if final_idx != -1:
        return AgentDecision(
            kind="final",
            final_answer=text[final_idx + len("\nFINAL:"):].strip(),
        )

    return AgentDecision(
        kind="final",
        final_answer=f"Model produced invalid format:\n{text}",
    )


class BaseModelClient:
    def decide_next_action(self, prompt: str) -> tuple[str, AgentDecision]:
        raise NotImplementedError

    def summarize_history(self, messages: List[Message]) -> str:
        raise NotImplementedError


class KimiModelClient(BaseModelClient):
    def __init__(
        self,
        model_name: str = "kimi-k2.5",
        api_key: Optional[str] = None,
        temperature: float = 0.6,
    ) -> None:
        self.model_name = model_name
        self.temperature = temperature
        self.client = OpenAI(
            api_key=api_key or os.environ.get("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1",
        )

    def _call_model(self, prompt: str) -> str:
        for attempt in range(3):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    temperature=self.temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                )
                return completion.choices[0].message.content.strip()
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = (attempt + 1) * 5
                    print(f"  [Rate limited, retrying in {wait}s...]")
                    time.sleep(wait)
                    continue
                raise

    def decide_next_action(self, prompt: str) -> tuple[str, AgentDecision]:
        raw = self._call_model(prompt)
        return raw, parse_agent_response(raw)

    def summarize_history(self, messages: List[Message]) -> str:
        history_text = []
        for msg in messages:
            label = msg.role.upper()
            if msg.name:
                label += f" ({msg.name})"
            history_text.append(f"[{label}]\n{msg.content}")

        prompt = (
            "Summarize the earlier coding-agent conversation.\n"
            "Focus on:\n"
            "1. current task goal\n"
            "2. key files inspected\n"
            "3. key facts discovered\n"
            "4. failed hypotheses or dead ends\n"
            "5. current likely next step\n\n"
            "Conversation:\n"
            + "\n\n".join(history_text)
        )
        return self._call_model(prompt)