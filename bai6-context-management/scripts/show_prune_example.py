"""In ví dụ rút gọn tool output của B1 (không cần API): output thô của tool và bản sau khi prune.

    python scripts/show_prune_example.py

Ứng với slide 19, 23: giữ dòng lỗi (gộp trùng, đếm số lần), gộp dòng lặp, bỏ phần còn lại; bản raw vẫn lưu ở archive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pruning import prune_tool_output  # noqa: E402
from tools.debug_tools import STATE, read_log, run_tests  # noqa: E402


def show(label: str, raw: str, pruned: str) -> None:
    print(f"{label}: thô {len(raw.splitlines())} dòng / {len(raw):,} ký tự → rút gọn {len(pruned.splitlines())} dòng / {len(pruned):,} ký tự "
          f"({len(pruned) / len(raw):.1%})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    STATE.reset()
    raw_log = read_log.invoke({"name": "checkout-api.log"})
    pruned_log = prune_tool_output(raw_log, "traces/archive/<id>.txt")
    raw_tests = run_tests.invoke({})
    pruned_tests = prune_tool_output(raw_tests, "traces/archive/<id>.txt")
    show("read_log('checkout-api.log')", raw_log, pruned_log)
    show("run_tests()", raw_tests, pruned_tests)
    print("\n--- read_log('checkout-api.log') sau khi rút gọn ---")
    print(pruned_log)
    print("\n--- run_tests() sau khi rút gọn ---")
    print(pruned_tests)
