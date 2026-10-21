"""Persistent memory: một file Markdown, mỗi quy ước một dòng.

Dòng active:      - [active] topic=report-format | rule=... | từ session-1 lúc 2026-10-21 09:30
Dòng bị thay thế: - [superseded 2026-10-21 09:35 bởi session-3] topic=report-format | rule=... | từ session-1 ...

Chỉ dòng active được nạp vào context. Dòng superseded giữ lại làm lịch sử và nguồn gốc thay đổi.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import paths

MEMORY_FILE = paths.PROJECT_ROOT / "memory" / "MEMORY.md"
HEADER = "# MEMORY: quy ước dự án đã thống nhất\n\n"

_ACTIVE = re.compile(r"^- \[active\] topic=(?P<topic>[^|]+) \| rule=(?P<rule>.+?) \| (?P<source>.+)$")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- [")]


def active_entries(path: Path = MEMORY_FILE) -> list[dict]:
    entries = []
    for line in _read_lines(path):
        match = _ACTIVE.match(line)
        if match:
            entries.append({k: v.strip() for k, v in match.groupdict().items()})
    return entries


def render_for_context(path: Path = MEMORY_FILE) -> str:
    """Khối text nạp vào system prompt. Rỗng nếu chưa có quy ước nào."""
    entries = active_entries(path)
    if not entries:
        return ""
    return "\n".join(f"- ({e['topic']}) {e['rule']}" for e in entries)


def save_convention(topic: str, rule: str, session_id: str, path: Path = MEMORY_FILE) -> dict:
    """Ghi quy ước. Nếu topic đã có dòng active thì đánh dấu superseded rồi thêm dòng mới."""
    topic = topic.strip().lower()
    rule = rule.strip().replace("|", "/").replace("\n", " ")
    if not topic or not rule:
        return {"ok": False, "error": "topic và rule không được rỗng"}

    lines = _read_lines(path)
    now = _now()
    replaced = False
    updated = []
    for line in lines:
        match = _ACTIVE.match(line)
        if match and match.group("topic").strip() == topic:
            body = line[len("- [active] "):]
            updated.append(f"- [superseded {now} bởi {session_id}] {body}")
            replaced = True
        else:
            updated.append(line)
    updated.append(f"- [active] topic={topic} | rule={rule} | từ {session_id} lúc {now}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "\n".join(updated) + "\n", encoding="utf-8")
    return {"ok": True, "topic": topic, "status": "updated" if replaced else "created"}


def reset(path: Path = MEMORY_FILE) -> None:
    path.unlink(missing_ok=True)
