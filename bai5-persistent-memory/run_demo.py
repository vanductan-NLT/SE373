"""Demo Challenge A: 4 session độc lập, memory là thứ duy nhất đi xuyên session.

    python run_demo.py --reset     # xóa memory + output rồi chạy lại từ đầu

Mỗi session dựng agent mới và history rỗng. In ra phần memory đã nạp, tool call, câu trả lời,
rồi code tự kiểm file báo cáo (không dựa vào lời agent tự khai). Toàn bộ output ghi thêm vào demo-log.txt.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import memory_store
import paths
from agent import build_agent, build_model
from config import RECURSION_LIMIT, load_settings

OUTPUT_DIR = paths.WORKSPACE_DIR / paths.OUTPUT_SUBDIR
LOG_PATH = paths.PROJECT_ROOT / "demo-log.txt"
TODAY = "2026-10-21"

S1_PROMPT = (
    "Mình chốt quy ước báo cáo cho dự án này: báo cáo tuần ghi vào file output/bao-cao-YYYY-MM-DD.md "
    "(YYYY-MM-DD là ngày hôm nay), viết bằng tiếng Việt, dòng đầu tiên của file bắt đầu bằng 'TL;DR:' "
    "tóm tắt một câu. Hãy ghi nhớ quy ước này."
)
WRITE_PROMPT = f"Hôm nay là {TODAY}. Đọc data/weekly_notes.md rồi viết báo cáo tuần."
S3_PROMPT = (
    "Mình đổi quy ước báo cáo: từ giờ file tên output/report-YYYY-MM-DD.md, viết bằng tiếng Anh, "
    "dòng đầu vẫn bắt đầu bằng 'TL;DR:'. Quy ước cũ bỏ. Hãy cập nhật ghi nhớ."
)

SESSIONS = [
    ("session-1", "Chốt quy ước (không có memory từ trước)", S1_PROMPT),
    ("session-2", "Viết báo cáo, KHÔNG nhắc lại quy ước", WRITE_PROMPT),
    ("session-3", "Đổi quy ước", S3_PROMPT),
    ("session-4", "Viết báo cáo, KHÔNG nhắc lại quy ước", WRITE_PROMPT),
]

_VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


class Tee:
    """Ghi đồng thời ra màn hình và file log."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)

    def flush(self):
        for s in self.streams:
            s.flush()


def show_tool_trace(messages: list) -> None:
    for m in messages:
        if m.type == "ai":
            for call in getattr(m, "tool_calls", None) or []:
                print(f"  [tool call] {call['name']}({call['args']})")
        elif m.type == "tool":
            text = str(m.content)
            print(f"  [tool result] {text[:160]}{'...' if len(text) > 160 else ''}")


def first_line(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line.strip()
    return ""


def check_report(path: Path, language: str) -> tuple[bool, str]:
    if not path.exists():
        return False, f"không thấy file {path.name}"
    text = path.read_text(encoding="utf-8")
    head = first_line(path)
    if not head.startswith("TL;DR:"):
        return False, f"dòng đầu không bắt đầu bằng 'TL;DR:': {head[:60]!r}"
    vi_ratio = len(_VI_CHARS.findall(text)) / max(len(text), 1)
    if language == "vi" and vi_ratio < 0.02:
        return False, f"nội dung không giống tiếng Việt (tỉ lệ dấu {vi_ratio:.3f})"
    if language == "en" and vi_ratio > 0.01:
        return False, f"nội dung còn tiếng Việt (tỉ lệ dấu {vi_ratio:.3f})"
    return True, f"{path.name} | dòng đầu: {head[:70]} | tỉ lệ dấu tiếng Việt {vi_ratio:.3f}"


def output_files() -> set[str]:
    return {p.name for p in OUTPUT_DIR.glob("*.md")} if OUTPUT_DIR.exists() else set()


def run_session(model, session_id: str, title: str, prompt: str) -> tuple[str, set[str]]:
    print(f"\n{'=' * 78}\n{session_id.upper()}: {title}\n{'=' * 78}")
    files_before = output_files()
    agent, memory_text = build_agent(model, session_id)
    print("MEMORY INJECTED vào system prompt:")
    print(memory_text if memory_text else "  (rỗng)")
    print(f"\nUSER: {prompt}")
    result = agent.invoke({"messages": [{"role": "user", "content": prompt}]}, config={"recursion_limit": RECURSION_LIMIT})
    messages = result["messages"]
    show_tool_trace(messages)
    print(f"AGENT: {messages[-1].content}")
    new_files = output_files() - files_before
    print(f"file MỚI do session này tạo trong output/: {sorted(new_files)}")
    return memory_text, new_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="xóa memory và output trước khi chạy")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    settings, missing = load_settings()
    if not settings:
        print("Thiếu cấu hình trong .env:", ", ".join(missing))
        return 2

    if args.reset:
        memory_store.reset()
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

    console = sys.stdout
    with LOG_PATH.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(console, log)
        try:
            return run_all(settings)
        finally:
            sys.stdout = console


def run_all(settings) -> int:
    model = build_model(settings)
    injected, created = {}, {}
    for session_id, title, prompt in SESSIONS:
        injected[session_id], created[session_id] = run_session(model, session_id, title, prompt)

    memory_text = memory_store.MEMORY_FILE.read_text(encoding="utf-8") if memory_store.MEMORY_FILE.exists() else ""
    banner = "=" * 78
    print(f"\n{banner}\nMEMORY.md cuối cùng\n{banner}")
    print(memory_text or "(không có)")

    print(f"{banner}\nKIỂM CHỨNG (do code kiểm file thực tế, không dựa vào lời agent)\n{banner}")
    old_name, new_name = f"bao-cao-{TODAY}.md", f"report-{TODAY}.md"

    ok1, why1 = check_report(OUTPUT_DIR / old_name, "vi")
    ok1 = ok1 and created["session-2"] == {old_name}
    print(f"Chứng minh 1 (session mới vẫn theo quy ước cũ): {'PASS' if ok1 else 'FAIL'} | session-2 tạo {sorted(created['session-2'])} | {why1}")

    ok2, why2 = check_report(OUTPUT_DIR / new_name, "en")
    ok2 = ok2 and created["session-4"] == {new_name}
    print(f"Chứng minh 2 (quy ước đổi, session sau theo quy ước mới): {'PASS' if ok2 else 'FAIL'} | session-4 tạo {sorted(created['session-4'])} | {why2}")

    print("Thông tin thêm (không tính PASS/FAIL):")
    print(f"  MEMORY.md giữ dòng superseded làm lịch sử? {'có' if '[superseded' in memory_text else 'không'}")
    print(f"  memory nạp vào session-4 còn nhắc quy ước cũ? {'CÓ' if 'bao-cao' in injected['session-4'] else 'không'}")
    return 0 if ok1 and ok2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
