from __future__ import annotations

import json
from dataclasses import asdict

from agent_types import Message, SessionState, TraceEntry
from context_manager import ContextManager
from models import BaseModelClient
from notes import NoteManager
from prompts import build_agent_prompt, build_system_prompt
from tools import ToolRegistry


class ClaudeStyleAgent:
    def __init__(
        self,
        model_client: BaseModelClient,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        note_manager: NoteManager,
        max_steps: int = 15,
        enable_compression: bool = True,
    ) -> None:
        self.model_client = model_client
        self.tool_registry = tool_registry
        self.context_manager = context_manager
        self.note_manager = note_manager
        self.max_steps = max_steps
        self.enable_compression = enable_compression
        self.trace: list[TraceEntry] = []

    def _maybe_compress(self, state: SessionState) -> bool:
        """Returns True if compression was actually performed."""
        if not self.enable_compression:
            return False

        if not self.context_manager.needs_compression(state.messages):
            return False

        result = self.context_manager.compress(
            state.messages,
            summarize_fn=self.model_client.summarize_history,
        )
        state.messages = result.kept_recent_messages
        return True

    def _append_tool_result(self, state: SessionState, result) -> None:
        if result.artifact_path:
            state.artifacts.append(result.artifact_path)

        state.messages.append(
            Message(
                role="tool",
                name=result.tool_name,
                content=(
                    f"Status: {'success' if result.ok else 'failure'}\n"
                    f"Summary: {result.summary}\n"
                    f"Content:\n{result.content}\n"
                    f"Artifact: {result.artifact_path or 'None'}"
                ),
            )
        )

    def _msg_total_chars(self, messages: list[Message]) -> int:
        return sum(len(m.content) for m in messages)

    def _save_trace(self, trace_path: str = "trace_output.json") -> None:
        data = [asdict(entry) for entry in self.trace]
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n[Trace] Saved {len(self.trace)} steps to {trace_path}")

    def run(self, user_task: str) -> str:
        self.trace = []
        state = SessionState(user_task=user_task)

        tool_desc = self.tool_registry.list_tools()
        system_prompt = build_system_prompt(tool_desc)

        state.messages.append(Message(role="system", content=system_prompt))
        state.messages.append(Message(role="user", content=user_task))

        mode = "compression=ON" if self.enable_compression else "compression=OFF"
        print(f"\n[Agent] Starting ({mode}, max_steps={self.max_steps})")
        print("-" * 60)

        for _ in range(self.max_steps):
            state.step_count += 1

            compressed = self._maybe_compress(state)

            prompt = build_agent_prompt(
                user_task=state.user_task,
                notes=self.note_manager.get_all(),
                messages=state.messages,
                tool_desc=tool_desc,
                step_count=state.step_count,
                max_steps=self.max_steps,
            )

            raw, decision = self.model_client.decide_next_action(prompt)
            state.messages.append(Message(role="assistant", content=raw))

            if decision.kind == "final":
                entry = TraceEntry(
                    step=state.step_count,
                    action="final",
                    model_raw=raw,
                    messages_count=len(state.messages),
                    messages_total_chars=self._msg_total_chars(state.messages),
                    compressed=compressed,
                )
                self.trace.append(entry)
                print(f"[Step {state.step_count}] FINAL ANSWER")
                print("-" * 60)
                self._save_trace()
                return decision.final_answer or "(empty final answer)"

            tool_call = decision.tool_call
            assert tool_call is not None

            if tool_call.tool_name == "save_note":
                text = str(tool_call.arguments.get("text", "")).strip()
                self.note_manager.add(text)
                state.messages.append(
                    Message(
                        role="tool",
                        name="save_note",
                        content=f"Status: success\nSummary: Saved note\nContent:\n{text}\nArtifact: None",
                    )
                )
                entry = TraceEntry(
                    step=state.step_count,
                    action="tool",
                    tool_name="save_note",
                    tool_args={"text": text},
                    tool_summary="Saved note",
                    model_raw=raw,
                    messages_count=len(state.messages),
                    messages_total_chars=self._msg_total_chars(state.messages),
                    compressed=compressed,
                )
                self.trace.append(entry)
                print(f"[Step {state.step_count}] save_note → Saved note | msgs={len(state.messages)} chars={self._msg_total_chars(state.messages)}{' [compressed]' if compressed else ''}")
                continue

            result = self.tool_registry.execute(tool_call)
            self._append_tool_result(state, result)

            entry = TraceEntry(
                step=state.step_count,
                action="tool",
                tool_name=tool_call.tool_name,
                tool_args=tool_call.arguments,
                tool_summary=result.summary,
                model_raw=raw,
                messages_count=len(state.messages),
                messages_total_chars=self._msg_total_chars(state.messages),
                compressed=compressed,
            )
            self.trace.append(entry)
            print(f"[Step {state.step_count}] {tool_call.tool_name}({_brief_args(tool_call.arguments)}) → {result.summary} | msgs={len(state.messages)} chars={self._msg_total_chars(state.messages)}{' [compressed]' if compressed else ''}")

        self._save_trace()
        return "FINAL:\nReached max steps without a final answer."


def _brief_args(args: dict) -> str:
    """Format tool arguments as a short string for console display."""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
