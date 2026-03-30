from __future__ import annotations

from agent import ClaudeStyleAgent
from context_manager import ContextManager
from models import KimiModelClient
from notes import NoteManager
from tools import ToolRegistry


def main() -> None:
    workspace_root = "./workspace"
    artifact_dir = "./artifacts"

    # ===== 实验开关 =====
    ENABLE_COMPRESSION = True       # 实验一：改为 False 关闭上下文压缩
    SEARCH_FILTER_MODE = "filtered" # 实验二：改为 "unfiltered" 关闭搜索过滤
    MAX_STEPS = 20                  # 给 agent 足够的步数空间
    # ====================

    context_manager = ContextManager(
        max_chars=12000,
        recent_keep=6,
        max_inline_chars=3000,
    )

    tool_registry = ToolRegistry(
        workspace_root=workspace_root,
        artifact_dir=artifact_dir,
        context_manager=context_manager,
        search_filter_mode=SEARCH_FILTER_MODE,
    )

    note_manager = NoteManager()

    model_client = KimiModelClient(
        model_name="kimi-k2.5",
        temperature=1,
    )

    agent = ClaudeStyleAgent(
        model_client=model_client,
        tool_registry=tool_registry,
        context_manager=context_manager,
        note_manager=note_manager,
        max_steps=MAX_STEPS,
        enable_compression=ENABLE_COMPRESSION,
    )

    task = input("Enter task: ").strip()
    answer = agent.run(task)

    print("\n=== FINAL ANSWER ===")
    print(answer)


if __name__ == "__main__":
    main()