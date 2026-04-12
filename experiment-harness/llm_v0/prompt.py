from __future__ import annotations

from pathlib import Path


class Prompt:
    def __init__(self, version_id: str, text: str, file_path: Path) -> None:
        self.version_id = version_id
        self.text = text
        self.file_path = file_path

    def update(self, diff: str, parent_version_id: str | None = None) -> str:
        header = ""
        if parent_version_id:
            header = f"# Applied diff from {parent_version_id}\n"
        self.text = f"{self.text.strip()}\n\n{header}{diff.strip()}".strip()
        return self.text

    def save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(self.text)
