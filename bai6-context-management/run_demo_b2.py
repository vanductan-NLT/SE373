"""Demo B2 (Code Mode, điểm cộng): CÙNG một câu hỏi, CÙNG bộ log, hai cách cho agent làm.

    python run_demo_b2.py                  # 50 file: native rồi Code Mode, sau đó thêm lượt 10 file
    python run_demo_b2.py --files 10       # chỉ một cỡ
    python run_demo_b2.py --mode code      # chỉ một chế độ (native | code)

- native : tools list_files + read_file. LLM tự đọc từng file, raw log đi vào context.
- code   : chỉ tool run_python. LLM viết chương trình, harness chạy, LLM chỉ nhận phần chương trình print.
Đo bằng `usage` của API: tổng input_tokens, số lần gọi model, số ký tự tool output quay về context, và đúng/sai
so với ground truth (fixtures/ground_truth.json, tính bằng cách parse lại chính các file log).
Nếu native tràn context hay chạm giới hạn số lần gọi thì đó cũng là một kết quả và được ghi lại.
Toàn bộ output ghi vào demo-b2.txt, số token từng lần gọi ghi vào traces/b2-*.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import unicodedata

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage

import paths
from agent import build_agent, build_model
from compaction import message_text
from config import (MODEL_CALL_LIMIT, NATIVE_MODEL_CALL_LIMIT, NATIVE_TOOL_CALL_LIMIT, RECURSION_LIMIT, TOOL_CALL_LIMIT,
                    load_settings)
from prompts import B2_CODE_MODE_SYSTEM_PROMPT, B2_NATIVE_SYSTEM_PROMPT
from token_log import TokenLogger
from tools.code_mode import run_python
from tools.files import list_files, read_file

LOG_PATH = paths.PROJECT_ROOT / "demo-b2.txt"


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


def ensure_logs() -> None:
    """Chưa có log hoặc đáp án thì sinh lại (deterministic, seed cố định)."""
    if not paths.GROUND_TRUTH_PATH.exists() or not any(paths.LOGS_DIR.glob("service-*.log")):
        subprocess.run([sys.executable, str(paths.FIXTURES_DIR / "make_logs.py")], check=True)


def expected_answer(n_files: int) -> dict:
    """Đáp án cho n file đầu, tính từ per_file trong ground truth."""
    truth = json.loads(paths.GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    names = [f"service-{i:02d}.log" for i in range(1, n_files + 1)]
    totals: dict[str, int] = {}
    for name in names:
        for error, n in truth["per_file"][name].items():
            totals[error] = totals.get(error, 0) + n
    top_error = max(totals, key=totals.get)
    counts = {name: truth["per_file"][name].get(top_error, 0) for name in names}
    best = max(counts.values())
    return {"error": top_error, "total": totals[top_error], "files": [n for n, c in counts.items() if c == best], "file_count": best}


def make_question(n_files: int) -> str:
    scope = "toàn bộ 50 file service-01.log … service-50.log" if n_files == 50 else f"chỉ {n_files} file đầu: service-01.log … service-{n_files:02d}.log"
    return (f"Trong các file log trong thư mục logs/ ({scope}), chỉ tính các dòng có mức ERROR (không tính WARN hay INFO): "
            "lỗi nào xuất hiện nhiều nhất? Cho biết tên lỗi, tổng số lần xuất hiện trên toàn bộ các file đó, và file có nhiều dòng ERROR "
            "của lỗi này nhất (kèm số lần trong file đó). Tên lỗi là từ đứng ngay sau 'ERROR [service-xx] ' và trước dấu ':'.")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").replace("đ", "d")


def grade(answer: str, expected: dict) -> list[tuple[str, bool]]:
    t = fold(answer)
    t = re.sub(r"(?<=\d)[.,](?=\d{3}(?!\d))", "", t)  # bỏ dấu phân cách hàng nghìn: 1,234 → 1234
    has_number = lambda n: re.search(rf"(?<!\d){n}(?!\d)", t) is not None  # noqa: E731
    return [
        (f"tên lỗi = {expected['error']}", expected["error"].lower() in t),
        (f"tổng = {expected['total']}", has_number(expected["total"])),
        (f"file = {'/'.join(expected['files'])}", any(f.replace('.log', '') in t for f in expected["files"])),
        (f"số lần trong file = {expected['file_count']}", has_number(expected["file_count"])),
    ]


def run_mode(settings, mode: str, n_files: int) -> dict:
    """Chạy một chế độ cho một cỡ n_files. Trả số đo và kết quả chấm."""
    native = mode == "native"
    logger = TokenLogger()
    tools = [list_files, read_file] if native else [run_python]
    limits = (NATIVE_MODEL_CALL_LIMIT, NATIVE_TOOL_CALL_LIMIT) if native else (MODEL_CALL_LIMIT, TOOL_CALL_LIMIT)
    agent = build_agent(
        build_model(settings), tools,
        [ModelCallLimitMiddleware(run_limit=limits[0], exit_behavior="end"), ToolCallLimitMiddleware(run_limit=limits[1])],
        B2_NATIVE_SYSTEM_PROMPT if native else B2_CODE_MODE_SYSTEM_PROMPT,
    )
    question = make_question(n_files)
    print(f"\n{'=' * 78}\nB2 · {mode.upper()} · {n_files} file\n{'=' * 78}\nUSER: {question}")
    started, status, answer, programs = time.time(), "OK", "", []
    try:
        result = agent.invoke({"messages": [HumanMessage(question)]}, config={"recursion_limit": RECURSION_LIMIT, "callbacks": [logger]})
        messages = result["messages"]
        answer = message_text(messages[-1])
        programs = [c["args"].get("code", "") for m in messages if isinstance(m, AIMessage) for c in m.tool_calls if c["name"] == "run_python"]
        if answer.startswith("Model call limits exceeded"):
            status, answer = f"CHẠM GIỚI HẠN MODEL CALL ({limits[0]})", ""
    except Exception as exc:  # tràn context của model là một kết quả hợp lệ của chế độ native
        text = str(exc)
        overflow = any(k in text.lower() for k in ("context length", "context_length", "maximum context", "too long", "too many tokens"))
        status = "TRÀN CONTEXT của model" if overflow else f"LỖI {type(exc).__name__}: {text[:160]}"
    elapsed = time.time() - started

    expected = expected_answer(n_files)
    checks = grade(answer, expected) if answer else []
    correct = bool(checks) and all(ok for _, ok in checks)
    print(f"[kết thúc] trạng thái: {status} | {len(logger.records)} lần gọi model | {logger.tool_calls} lần chạy tool | {elapsed:.0f}s")
    if programs:
        print("Chương trình model viết ở lần chạy cuối:\n" + programs[-1])
    print(f"AGENT: {answer or '(không có câu trả lời)'}")
    print(f"Đáp án đúng: {expected['error']} {expected['total']} lần; file {'/'.join(expected['files'])} {expected['file_count']} lần")
    for name, ok in checks:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    logger.write_jsonl(paths.TRACES_DIR / f"b2-{mode}-{n_files}files.jsonl")
    return {"mode": mode, "files": n_files, "status": status, "totals": logger.totals(), "tool_calls": logger.tool_calls,
            "tool_chars": logger.tool_output_chars, "correct": correct, "answered": bool(answer), "seconds": elapsed}


def print_summary(rows: list[dict]) -> None:
    print(f"\n{'=' * 78}\nSO SÁNH (cùng câu hỏi, cùng bộ log; token đo bằng `usage` của API)\n{'=' * 78}")
    print(f"{'chế độ':<7} {'file':>4} {'lần gọi':>7} {'tool':>5} {'input tổng':>11} {'input đỉnh':>11} {'tool output→context':>20} {'đúng?':>6}  trạng thái")
    for r in rows:
        t = r["totals"]
        verdict = "ĐÚNG" if r["correct"] else ("SAI" if r["answered"] else "không có")
        print(f"{r['mode']:<7} {r['files']:>4} {t['calls']:>7} {r['tool_calls']:>5} {t['input_total']:>11,} {t['input_peak']:>11,} "
              f"{r['tool_chars']:>17,} ký tự {verdict:>6}  {r['status']}")
    by_size: dict[int, dict] = {}
    for r in rows:
        by_size.setdefault(r["files"], {})[r["mode"]] = r
    for size, pair in sorted(by_size.items(), reverse=True):
        if "native" in pair and "code" in pair and pair["code"]["totals"]["input_total"]:
            ratio = pair["native"]["totals"]["input_total"] / pair["code"]["totals"]["input_total"]
            print(f"{size} file: native tốn gấp {ratio:.1f} lần input tokens của Code Mode"
                  f"{'' if pair['native']['answered'] else ' (và native không trả lời được)'}.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, choices=range(1, 51), metavar="N", help="chỉ chạy một cỡ N file (mặc định: 50 rồi 10)")
    parser.add_argument("--mode", choices=["native", "code"], help="chỉ chạy một chế độ (mặc định: cả hai)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    settings, missing = load_settings()
    if not settings:
        print("Thiếu cấu hình trong .env:", ", ".join(missing))
        return 2
    ensure_logs()

    sizes = [args.files] if args.files else [50, 10]
    modes = [args.mode] if args.mode else ["native", "code"]
    console = sys.stdout
    with LOG_PATH.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(console, log)
        try:
            rows = [run_mode(settings, mode, size) for size in sizes for mode in modes]
            print_summary(rows)
            code_rows = [r for r in rows if r["mode"] == "code"]
            ok = bool(code_rows) and all(r["correct"] for r in code_rows)
            print(f"\nKẾT QUẢ B2 (Code Mode trả lời đúng ground truth ở mọi cỡ): {'PASS' if ok else 'FAIL'}")
            return 0 if ok else 1
        finally:
            sys.stdout = console


if __name__ == "__main__":
    raise SystemExit(main())
