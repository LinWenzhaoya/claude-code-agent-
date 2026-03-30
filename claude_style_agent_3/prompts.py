from __future__ import annotations

from typing import List

from agent_types import Message


def build_system_prompt(tool_desc: str) -> str:
    return f"""You are a careful coding agent.

Core behavior rules:
1. You do NOT know the repository unless you inspect it with tools.
2. Prefer search before guessing.
3. Read only the file regions you need.
4. Do not invent code details you have not seen.
5. Keep the main task in mind and avoid random exploration.
6. If you discover an important fact or next-step plan, you may use save_note to preserve it.
7. Your response MUST begin with either TOOL: or FINAL: on the very first line. Do not write any explanation before it. Respond in exactly one of the following formats:

TOOL:
{{"tool_name":"...","arguments":{{...}}}}

or

FINAL:
<your final answer>

Available tools:
{tool_desc}
"""


def render_notes(notes: List[str]) -> str:
    if not notes:
        return "No saved notes yet."
    return "\n".join(f"{idx+1}. {note}" for idx, note in enumerate(notes))


def render_messages(messages: List[Message]) -> str:
    chunks: List[str] = []
    for msg in messages:
        label = msg.role.upper()
        if msg.name:
            label += f" ({msg.name})"
        chunks.append(f"[{label}]\n{msg.content}")
    return "\n\n".join(chunks)


def build_agent_prompt(
    user_task: str,
    notes: List[str],
    messages: List[Message],
    tool_desc: str,
    step_count: int,
    max_steps: int,
) -> str:
    return f"""Task:
{user_task}

Working notes:
{render_notes(notes)}

Available tools:
{tool_desc}

Conversation so far:
{render_messages(messages)}

Current step: {step_count}
Max steps: {max_steps}

Decide the single best next step.
Remember:
- If you need more information, call a tool.
- If you have enough information, produce FINAL.
- Do not output both.
"""