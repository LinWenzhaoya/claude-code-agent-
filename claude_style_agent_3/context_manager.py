from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Tuple

from agent_types import CompressionResult, Message


class ContextManager:
    """
    负责：
    1. 判断上下文是否过长
    2. 压缩旧历史
    3. 长输出外存化
    """

    def __init__(
        self,
        max_chars: int = 15000,
        recent_keep: int = 6,
        max_inline_chars: int = 4000,
    ) -> None:
        self.max_chars = max_chars
        self.recent_keep = recent_keep
        self.max_inline_chars = max_inline_chars

    def estimate_chars(self, messages: List[Message]) -> int:
        total = 0
        for msg in messages:
            total += len(msg.role) + len(msg.content)
            if msg.name:
                total += len(msg.name)
        return total

    def needs_compression(self, messages: List[Message]) -> bool:
        return self.estimate_chars(messages) > self.max_chars

    def compress(
        self,
        messages: List[Message],
        summarize_fn: Callable[[List[Message]], str],
    ) -> CompressionResult:
        """
        压缩策略：
        - 默认保留第一条 system message（如果有）
        - 保留最近 recent_keep 条原始消息
        - 中间历史压成一条 summary message
        """
        if not messages:
            return CompressionResult(
                summary_message=Message(role="system", content=""),
                kept_recent_messages=[],
            )

        system_messages = [m for m in messages if m.role == "system"]
        first_system = system_messages[0] if system_messages else None

        body_messages = messages[:]
        if first_system is not None and body_messages and body_messages[0] == first_system:
            body_messages = body_messages[1:]

        if len(body_messages) <= self.recent_keep:
            summary_text = "No compression needed yet."
            return CompressionResult(
                summary_message=Message(
                    role="system",
                    content=f"Conversation summary:\n{summary_text}",
                ),
                kept_recent_messages=body_messages,
            )

        old_messages = body_messages[:-self.recent_keep]
        recent_messages = body_messages[-self.recent_keep:]

        summary_text = summarize_fn(old_messages)

        summary_message = Message(
            role="system",
            content=(
                "Conversation summary of earlier context:\n"
                f"{summary_text}\n\n"
                "Use this summary as compressed memory of prior steps."
            ),
        )

        kept_recent = []
        if first_system is not None:
            kept_recent.append(first_system)
        kept_recent.append(summary_message)
        kept_recent.extend(recent_messages)

        return CompressionResult(
            summary_message=summary_message,
            kept_recent_messages=kept_recent,
        )

    def maybe_store_artifact(
        self,
        text: str,
        prefix: str,
        artifact_dir: str,
    ) -> Tuple[str, str | None]:
        """
        如果 text 太长：
        - 完整内容写入 artifact 文件
        - 返回截断后的 inline 文本 + artifact_path
        """
        if len(text) <= self.max_inline_chars:
            return text, None

        artifact_root = Path(artifact_dir)
        artifact_root.mkdir(parents=True, exist_ok=True)

        existing = sorted(artifact_root.glob(f"{prefix}_*.txt"))
        next_index = len(existing) + 1
        artifact_path = artifact_root / f"{prefix}_{next_index:03d}.txt"
        artifact_path.write_text(text, encoding="utf-8")

        head = text[:2000]
        tail = text[-1200:]

        truncated = (
            f"{head}\n\n"
            "... [TRUNCATED, middle omitted] ...\n\n"
            f"{tail}\n\n"
            f"Full output saved to: {artifact_path}"
        )
        return truncated, str(artifact_path)