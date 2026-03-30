from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class Message:
    role: Role
    content: str
    name: Optional[str] = None


@dataclass
class ToolCall:
    tool_name: str
    arguments: Dict[str, Any]


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    summary: str
    content: str
    artifact_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AgentDecision:
    kind: Literal["tool", "final"]
    tool_call: Optional[ToolCall] = None
    final_answer: Optional[str] = None


@dataclass
class SessionState:
    user_task: str
    messages: List[Message] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    step_count: int = 0


@dataclass
class CompressionResult:
    summary_message: Message
    kept_recent_messages: List[Message]


@dataclass
class TraceEntry:
    step: int
    action: str  # "tool" or "final"
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_summary: Optional[str] = None
    model_raw: Optional[str] = None
    messages_count: int = 0
    messages_total_chars: int = 0
    compressed: bool = False