from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List, Optional

from agent_types import ToolCall, ToolResult
from context_manager import ContextManager


class ToolRegistry:
    """
    Claude-style minimal tool registry.

    Safety principles for this stage:
    1. Only operate inside workspace_root.
    2. run_command is whitelist-based.
    3. write_patch only does snippet replacement, not full-file overwrite.
    """

    def __init__(
        self,
        workspace_root: str,
        artifact_dir: str = "artifacts",
        context_manager: Optional[ContextManager] = None,
        search_filter_mode: str = "filtered",
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.artifact_dir = Path(artifact_dir).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

        self.context_manager = context_manager or ContextManager()
        self.search_filter_mode = search_filter_mode  # "filtered" or "unfiltered"

        # 只允许非常有限的一组命令
        self.allowed_command_prefixes = [
            ["pytest"],
            ["python", "-m", "pytest"],
            ["python3", "-m", "pytest"],
            ["python"],
            ["python3"],
            ["ls"],
            ["cat"],
        ]

    def list_tools(self) -> str:
        return (
            "Available tools:\n"
            "1. list_dir(path: str)\n"
            "   - List one directory level under the workspace.\n"
            "2. search_code(query: str, path: str='.')\n"
            "   - Search text in files under a path. Returns up to 20 matches.\n"
            "3. read_file(path: str, start_line: int|None=None, end_line: int|None=None)\n"
            "   - Read a file segment. Returns at most 150 lines.\n"
            "4. write_patch(path: str, old_snippet: str, new_snippet: str)\n"
            "   - Replace one snippet in one file. Minimal patch only.\n"
            "5. run_command(cmd: str)\n"
            "   - Run a whitelisted command inside workspace. Long output may be stored as artifact.\n"
            "6. save_note(text: str)\n"
            "   - Save a working note (handled by agent layer).\n"
        )

    def execute(self, call: ToolCall) -> ToolResult:
        tool_name = call.tool_name
        args = call.arguments or {}

        if tool_name == "list_dir":
            return self.tool_list_dir(path=args.get("path", "."))
        if tool_name == "search_code":
            return self.tool_search_code(
                query=args.get("query", ""),
                path=args.get("path", "."),
            )
        if tool_name == "read_file":
            return self.tool_read_file(
                path=args.get("path", ""),
                start_line=args.get("start_line"),
                end_line=args.get("end_line"),
            )
        if tool_name == "write_patch":
            return self.tool_write_patch(
                path=args.get("path", ""),
                old_snippet=args.get("old_snippet", ""),
                new_snippet=args.get("new_snippet", ""),
            )
        if tool_name == "run_command":
            return self.tool_run_command(cmd=args.get("cmd", ""))

        return ToolResult(
            tool_name=tool_name,
            ok=False,
            summary=f"Unknown tool: {tool_name}",
            content=f"Tool '{tool_name}' is not supported.",
        )

    def _resolve_path(self, relative_path: str) -> Path:
        candidate = (self.workspace_root / relative_path).resolve()
        if not str(candidate).startswith(str(self.workspace_root)):
            raise ValueError("Path escapes workspace root.")
        return candidate

    def _is_text_file(self, path: Path) -> bool:
        binary_suffixes = {
            ".png", ".jpg", ".jpeg", ".gif", ".webp",
            ".pdf", ".zip", ".tar", ".gz", ".so", ".dll", ".exe",
            ".pyc", ".ipynb", ".xlsx", ".xls", ".docx", ".pptx",
        }
        return path.suffix.lower() not in binary_suffixes

    def _store_if_needed(self, text: str, prefix: str) -> tuple[str, str | None]:
        return self.context_manager.maybe_store_artifact(
            text=text,
            prefix=prefix,
            artifact_dir=str(self.artifact_dir),
        )

    def _make_backup(self, file_path: Path) -> Path:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path

    def _command_allowed(self, cmd: str) -> tuple[bool, str]:
        if not cmd.strip():
            return False, "Empty command."

        try:
            parts = shlex.split(cmd)
        except Exception as e:
            return False, f"Failed to parse command: {e}"

        if not parts:
            return False, "Empty command after parsing."

        for prefix in self.allowed_command_prefixes:
            if parts[: len(prefix)] == prefix:
                return True, "Allowed by whitelist."

        return False, (
            "Command is not in whitelist. "
            f"Allowed prefixes: {self.allowed_command_prefixes}"
        )

    def tool_list_dir(self, path: str = ".") -> ToolResult:
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return ToolResult(
                    tool_name="list_dir",
                    ok=False,
                    summary=f"Path not found: {path}",
                    content=f"Directory '{path}' does not exist.",
                )
            if not target.is_dir():
                return ToolResult(
                    tool_name="list_dir",
                    ok=False,
                    summary=f"Not a directory: {path}",
                    content=f"'{path}' is not a directory.",
                )

            entries = sorted(list(target.iterdir()), key=lambda p: (p.is_file(), p.name.lower()))
            entries = entries[:100]

            rendered: List[str] = []
            for entry in entries:
                prefix = "[D]" if entry.is_dir() else "[F]"
                rendered.append(f"{prefix} {entry.name}")

            content = "\n".join(rendered) if rendered else "(empty directory)"
            return ToolResult(
                tool_name="list_dir",
                ok=True,
                summary=f"Listed {len(entries)} entries under '{path}'.",
                content=content,
                metadata={"entry_count": len(entries)},
            )
        except Exception as e:
            return ToolResult(
                tool_name="list_dir",
                ok=False,
                summary="list_dir failed",
                content=str(e),
            )

    def tool_search_code(self, query: str, path: str = ".") -> ToolResult:
        if not query.strip():
            return ToolResult(
                tool_name="search_code",
                ok=False,
                summary="Empty query",
                content="The search query cannot be empty.",
            )

        try:
            root = self._resolve_path(path)
            if not root.exists():
                return ToolResult(
                    tool_name="search_code",
                    ok=False,
                    summary=f"Path not found: {path}",
                    content=f"Search root '{path}' does not exist.",
                )

            search_root = root if root.is_dir() else root.parent

            # unfiltered: collect up to 100 matches; filtered: also collect all first
            max_collect = 100
            matches: List[str] = []
            files_scanned = 0

            for file_path in search_root.rglob("*"):
                if len(matches) >= max_collect:
                    break
                if not file_path.is_file():
                    continue
                if not self._is_text_file(file_path):
                    continue

                try:
                    files_scanned += 1
                    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                        for lineno, line in enumerate(f, start=1):
                            if query.lower() in line.lower():
                                rel = file_path.relative_to(self.workspace_root)
                                matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                                if len(matches) >= max_collect:
                                    break
                except Exception:
                    continue

            if not matches:
                return ToolResult(
                    tool_name="search_code",
                    ok=True,
                    summary=f"No matches found for '{query}'.",
                    content="No matches found.",
                    metadata={"files_scanned": files_scanned, "match_count": 0},
                )

            total_found = len(matches)

            if self.search_filter_mode == "filtered":
                # Only return top 5, with a summary note
                shown = matches[:5]
                content = (
                    f"Found {total_found} matches total. Showing top 5 most relevant:\n\n"
                    + "\n".join(shown)
                )
            else:
                # unfiltered: return everything
                content = "\n".join(matches)

            inline_content, artifact_path = self._store_if_needed(content, "search")

            return ToolResult(
                tool_name="search_code",
                ok=True,
                summary=f"Found {total_found} matches for '{query}'.",
                content=inline_content,
                artifact_path=artifact_path,
                metadata={"files_scanned": files_scanned, "match_count": total_found},
            )
        except Exception as e:
            return ToolResult(
                tool_name="search_code",
                ok=False,
                summary="search_code failed",
                content=str(e),
            )

    def tool_read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> ToolResult:
        if not path:
            return ToolResult(
                tool_name="read_file",
                ok=False,
                summary="Missing path",
                content="Parameter 'path' is required.",
            )

        try:
            file_path = self._resolve_path(path)
            if not file_path.exists():
                return ToolResult(
                    tool_name="read_file",
                    ok=False,
                    summary=f"File not found: {path}",
                    content=f"File '{path}' does not exist.",
                )
            if not file_path.is_file():
                return ToolResult(
                    tool_name="read_file",
                    ok=False,
                    summary=f"Not a file: {path}",
                    content=f"'{path}' is not a file.",
                )
            if not self._is_text_file(file_path):
                return ToolResult(
                    tool_name="read_file",
                    ok=False,
                    summary=f"Unsupported file type: {path}",
                    content="This tool only supports text-like files in the first version.",
                )

            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total_lines = len(lines)

            start = 1 if start_line is None else max(1, int(start_line))
            end = min(total_lines, start + 149) if end_line is None else min(total_lines, int(end_line))

            if end < start:
                end = start

            if end - start + 1 > 150:
                end = start + 149

            sliced = lines[start - 1:end]
            rendered = []
            for idx, line in enumerate(sliced, start=start):
                rendered.append(f"{idx:>4}: {line.rstrip()}")

            content = "\n".join(rendered)
            inline_content, artifact_path = self._store_if_needed(content, "read")

            return ToolResult(
                tool_name="read_file",
                ok=True,
                summary=f"Read {path} lines {start}-{end} (total {total_lines}).",
                content=inline_content,
                artifact_path=artifact_path,
                metadata={"path": path, "start_line": start, "end_line": end, "total_lines": total_lines},
            )
        except Exception as e:
            return ToolResult(
                tool_name="read_file",
                ok=False,
                summary="read_file failed",
                content=str(e),
            )

    def tool_write_patch(
        self,
        path: str,
        old_snippet: str,
        new_snippet: str,
    ) -> ToolResult:
        if not path:
            return ToolResult(
                tool_name="write_patch",
                ok=False,
                summary="Missing path",
                content="Parameter 'path' is required.",
            )
        if not old_snippet:
            return ToolResult(
                tool_name="write_patch",
                ok=False,
                summary="Missing old_snippet",
                content="Parameter 'old_snippet' must be non-empty.",
            )

        try:
            file_path = self._resolve_path(path)
            if not file_path.exists():
                return ToolResult(
                    tool_name="write_patch",
                    ok=False,
                    summary=f"File not found: {path}",
                    content=f"File '{path}' does not exist.",
                )
            if not file_path.is_file():
                return ToolResult(
                    tool_name="write_patch",
                    ok=False,
                    summary=f"Not a file: {path}",
                    content=f"'{path}' is not a file.",
                )
            if not self._is_text_file(file_path):
                return ToolResult(
                    tool_name="write_patch",
                    ok=False,
                    summary="Unsupported file type",
                    content="Only text-like files are supported.",
                )

            original = file_path.read_text(encoding="utf-8")

            occurrences = original.count(old_snippet)
            if occurrences == 0:
                return ToolResult(
                    tool_name="write_patch",
                    ok=False,
                    summary="Snippet not found",
                    content="The provided old_snippet was not found in the file.",
                )
            if occurrences > 1:
                return ToolResult(
                    tool_name="write_patch",
                    ok=False,
                    summary="Snippet is ambiguous",
                    content=(
                        "The provided old_snippet appears multiple times in the file. "
                        "Please provide a more specific snippet."
                    ),
                )

            backup_path = self._make_backup(file_path)
            updated = original.replace(old_snippet, new_snippet, 1)
            file_path.write_text(updated, encoding="utf-8")

            diff_preview = (
                "Patch applied successfully.\n\n"
                "OLD:\n"
                f"{old_snippet}\n\n"
                "NEW:\n"
                f"{new_snippet}\n"
            )
            inline_content, artifact_path = self._store_if_needed(diff_preview, "patch")

            return ToolResult(
                tool_name="write_patch",
                ok=True,
                summary=f"Patched file '{path}'. Backup created at '{backup_path.name}'.",
                content=inline_content,
                artifact_path=artifact_path,
                metadata={"path": path, "backup_path": str(backup_path)},
            )
        except Exception as e:
            return ToolResult(
                tool_name="write_patch",
                ok=False,
                summary="write_patch failed",
                content=str(e),
            )

    def tool_run_command(self, cmd: str) -> ToolResult:
        allowed, reason = self._command_allowed(cmd)
        if not allowed:
            return ToolResult(
                tool_name="run_command",
                ok=False,
                summary="Command rejected",
                content=reason,
            )

        try:
            completed = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = (
                f"$ {cmd}\n\n"
                f"[exit_code] {completed.returncode}\n\n"
                f"[stdout]\n{completed.stdout}\n\n"
                f"[stderr]\n{completed.stderr}"
            ).strip()

            inline_content, artifact_path = self._store_if_needed(output, "command")

            ok = completed.returncode == 0
            summary = (
                f"Command finished with exit code {completed.returncode}."
                if ok
                else f"Command failed with exit code {completed.returncode}."
            )

            return ToolResult(
                tool_name="run_command",
                ok=ok,
                summary=summary,
                content=inline_content,
                artifact_path=artifact_path,
                metadata={"cmd": cmd, "exit_code": completed.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="run_command",
                ok=False,
                summary="Command timed out",
                content=f"Command timed out after 30 seconds: {cmd}",
            )
        except Exception as e:
            return ToolResult(
                tool_name="run_command",
                ok=False,
                summary="run_command failed",
                content=str(e),
            )