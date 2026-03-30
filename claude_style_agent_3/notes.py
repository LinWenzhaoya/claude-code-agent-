from __future__ import annotations


class NoteManager:
    def __init__(self) -> None:
        self._notes: list[str] = []

    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self._notes.append(text)

    def get_all(self) -> list[str]:
        return list(self._notes)

    def render_for_prompt(self) -> str:
        if not self._notes:
            return "No saved notes yet."
        return "\n".join(f"{idx+1}. {note}" for idx, note in enumerate(self._notes))