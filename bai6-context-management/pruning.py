"""Prune tool output (slide 19, 23): giữ dòng lỗi/FAIL + tổng kết, gộp dòng lặp, archive bản raw ra file.

Ứng với slide 23: KEEP dòng lỗi chưa giải quyết, TRUNCATE output dài còn vài dòng chính,
DROP log trùng (gộp thành "lặp N lần"). Bản raw không mất: ghi ở traces/archive/<id>.txt,
và tool deterministic nên agent có thể gọi lại khi thật sự cần.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import paths
from config import PRUNE_MAX_KEY_LINES

PRUNED_MARKER = "[ĐÃ RÚT GỌN"

# Dòng "quan trọng": mức ERROR/FATAL, FAILED, traceback, dòng "E   ..." của pytest, "XxxError: ...", dòng tổng kết pytest.
_KEY_LINE = re.compile(
    r"\b(ERROR|FATAL|CRITICAL|FAILED|FAIL)\b|Traceback|^E\s|\b\w+(Error|Exception):|^=+ .*\b(passed|failed)\b.* =+$"
)
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?\s*")


def _group_key(line: str) -> str:
    """Khoá để gộp dòng "giống nhau": bỏ timestamp, thay mọi số bằng #."""
    return re.sub(r"\d+", "#", _TIMESTAMP.sub("", line)).strip()


def _with_count(line: str, count: int) -> str:
    return f"(×{count}) {line}" if count > 1 else line


def prune_tool_output(text: str, archive_ref: str) -> str:
    """Rút gọn một tool output dài. archive_ref là đường dẫn archive đưa vào dòng đầu cho người đọc."""
    lines = text.splitlines()
    key_groups: dict[str, list] = {}  # khoá → [dòng đầu tiên, số lần]
    noise = Counter()
    noise_sample: dict[str, str] = {}
    for line in lines[1:]:  # dòng đầu là tiêu đề tool, giữ riêng bên dưới
        if not line.strip():
            continue
        key = _group_key(line)
        if _KEY_LINE.search(line):
            key_groups.setdefault(key, [line, 0])[1] += 1
        else:
            noise[key] += 1
            noise_sample.setdefault(key, _TIMESTAMP.sub("", line).strip())

    shown = list(key_groups.values())[:PRUNE_MAX_KEY_LINES]
    hidden = len(key_groups) - len(shown)
    repeated = [(k, n) for k, n in noise.most_common(5) if n >= 5]
    kept = 2 + len(shown) + len(repeated)

    out = [
        f"{PRUNED_MARKER} tool output: {len(lines):,} dòng / {len(text):,} ký tự → còn ~{kept} dòng. "
        f"Bản đầy đủ: {archive_ref} (cần raw thì gọi lại tool).]",
        lines[0] if lines else "",
        "-- Dòng lỗi / FAIL (đã gộp trùng) --",
    ]
    out += [_with_count(first, count) for first, count in shown] or ["(không có)"]
    if hidden > 0:
        out.append(f"(… còn {hidden} nhóm dòng lỗi khác, xem bản đầy đủ)")
    if repeated:
        out.append("-- Dòng lặp đã gộp --")
        out += [f"(×{n:,}) {noise_sample[k]}" for k, n in repeated]
    out += ["-- Dòng cuối --", lines[-1] if lines else ""]
    return "\n".join(out)


def archive_raw(name: str, text: str) -> Path:
    """Ghi bản raw ra traces/archive/<name>.txt (name đã làm sạch để dùng làm tên file)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    paths.ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = paths.ARCHIVE_DIR / f"{safe}.txt"
    path.write_text(text, encoding="utf-8")
    return path
