"""Demo B1 (Compact): session debug dài, compact kích hoạt, agent vẫn nhớ lỗi / cách đã thử / bước tiếp.

    python run_demo_b1.py               # chạy có compact, rồi chạy đối chứng không compact
    python run_demo_b1.py --no-baseline # bỏ phần đối chứng

Luồng: 5 lượt user cố định (nêu mục tiêu + ràng buộc, đọc log, chạy test, thử fix sai, đọc thêm log) cho tới khi compact chạy;
rồi hỏi lại "đang điều tra gì / đã thử gì / ràng buộc / bước tiếp" và cho agent làm tiếp (slide 22: kiểm chứng checkpoint
bằng cách cho agent tiếp tục task). Code tự chấm PASS/FAIL bằng keyword, không dựa vào lời agent tự khai.
Toàn bộ output ghi thêm vào demo-b1.txt, số token từng lần gọi model ghi vào traces/*.jsonl.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import paths
from agent import build_agent, build_model
from compaction import Checkpoint, CompactionMiddleware, message_text
from config import MODEL_CALL_LIMIT, RECURSION_LIMIT, TOOL_CALL_LIMIT, load_settings
from prompts import B1_SYSTEM_PROMPT
from token_log import TokenLogger
from tools.debug_tools import STATE, apply_fix, read_log, run_tests

LOG_PATH = paths.PROJECT_ROOT / "demo-b1.txt"

TURNS = [
    ("T1", "Mình đang điều tra lỗi: API POST /checkout thỉnh thoảng trả HTTP 500. Ràng buộc: KHÔNG đổi API công khai /checkout "
           "(path, request, response giữ nguyên) và KHÔNG restart production. Bước đầu: đọc checkout-api.log và cho mình biết lỗi chính."),
    ("T2", "Chạy bộ test xem test nào đang fail."),
    ("T3", "Thử fix nhanh: tăng timeout kết nối DB lên 30 giây (gọi apply_fix), rồi chạy lại test."),
    ("T4", "Đọc thêm db-pool.log xem có gì liên quan."),
    ("T5", "Đọc thêm payment-gateway.log để đối chiếu."),
]
FILLER_TURN = "Đọc lại checkout-api.log lần nữa, so sánh với những gì đã biết."  # chỉ dùng nếu 5 lượt chưa đủ để kích hoạt compact
FINAL_QUESTION = ("Tạm dừng. Cho mình biết ngắn gọn: (1) Đang điều tra lỗi gì? (2) Đã thử cách nào và kết quả ra sao? "
                  "(3) Mình đã đặt ràng buộc gì? (4) Bước tiếp theo bạn đề xuất?")
CONTINUE_TURN = "Ok, làm bước tiếp theo bạn vừa đề xuất: gọi apply_fix với mô tả cụ thể, rồi chạy lại test."


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


def fold(text: str) -> str:
    """Hạ chữ thường và bỏ dấu tiếng Việt để so keyword không phụ thuộc cách gõ dấu."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").replace("đ", "d")


# Cụm (đã bỏ dấu) cho thấy cách "tăng timeout" không hiệu quả; phải nằm gần chữ "timeout" mới tính (chữ "van", "chua" đứng riêng quá dễ trùng).
NEGATIVE_OUTCOME_PHRASES = ("khong cai thien", "khong hieu qua", "khong co tac dung", "khong giai quyet", "khong khac phuc", "khong sua duoc",
                            "van fail", "van loi", "van that bai", "van con loi", "that bai", "vo ich", "vo nghia", "y het")
# Cụm (đã bỏ dấu) cho thấy bước tiếp là giải phóng kết nối DB; chỉ nhắc payment/gateway thôi thì chưa đủ.
RELEASE_PHRASES = ("giai phong", "release", "close", "dong connection", "dong ket noi", "tra connection", "tra ket noi", "tra ve pool", "tra lai",
                   "nha connection", "nha ket noi", "leak", "ro ri", "thu hep")


def near(text: str, anchor: str, phrases: tuple, window: int = 300) -> bool:
    """True nếu một cụm trong phrases nằm trong `window` ký tự quanh một lần xuất hiện của anchor."""
    return any(any(p in text[max(0, m.start() - window): m.end() + window] for p in phrases) for m in re.finditer(anchor, text))


def grade_final_answer(answer: str) -> list[tuple[str, bool, str]]:
    """Chấm câu trả lời sau compact bằng keyword ground truth (kiểm tra thô, không thay cho người đọc)."""
    t = fold(answer)
    has = lambda words: any(w in t for w in words)  # noqa: E731
    return [
        ("lỗi đang điều tra", "/checkout" in t and has(["500", "dbpool", "pool"]), "nhắc /checkout và (500 hoặc pool)"),
        ("cách đã thử + kết quả", near(t, "timeout", NEGATIVE_OUTCOME_PHRASES), "nhắc tăng timeout và việc nó không hiệu quả (cụm phủ định gần chữ timeout)"),
        ("ràng buộc (không đổi API)", "api" in t and has(["khong doi", "giu nguyen", "khong thay doi", "khong duoc doi", "bat bien"]), "nhắc giữ nguyên API công khai"),
        ("bước tiếp theo hợp lý", has(["connection", "ket noi", "pool"]) and has(RELEASE_PHRASES), "nhắc giải phóng/nhả kết nối DB"),
    ]


def print_turn_trace(new_messages: list) -> None:
    for m in new_messages:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                print(f"  [tool call] {call['name']}({call['args']})")
            if message_text(m).strip():
                print(f"AGENT: {message_text(m)}")
        elif isinstance(m, ToolMessage):
            text = message_text(m)
            print(f"  [tool result] {m.name}: {len(text):,} ký tự | {text[:100].splitlines()[0] if text else ''}")


def run_turn(agent, messages: list, text: str, label: str, logger: TokenLogger) -> tuple[list, list]:
    """Một lượt user: gửi toàn bộ history + câu mới. Trả (history mới, các message mới sinh ra trong lượt)."""
    logger.turn = label
    print(f"\n{'-' * 78}\n{label} USER: {text}")
    seen = {m.id for m in messages}
    result = agent.invoke({"messages": messages + [HumanMessage(text)]},
                          config={"recursion_limit": RECURSION_LIMIT, "callbacks": [logger]})
    history = result["messages"]
    new = [m for m in history if m.id not in seen and not m.additional_kwargs.get("compacted")]
    print_turn_trace(new)
    last_calls = [r for r in logger.records if r["turn"] == label and r["kind"] == "agent"]
    print(f"  [ctx] {len(history)} messages; input_tokens lần gọi model cuối của lượt: {last_calls[-1]['input_tokens'] if last_calls else '?'}")
    return history, new


def run_session(settings, compact: bool) -> dict:
    """Chạy trọn kịch bản một lần (có hoặc không compact). Trả kết quả để in bảng và chấm."""
    STATE.reset()
    logger = TokenLogger()
    middleware = [ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="end"), ToolCallLimitMiddleware(run_limit=TOOL_CALL_LIMIT)]
    compaction = None
    if compact:
        compaction = CompactionMiddleware(build_model(settings, thinking=False), token_logger=logger)
        middleware.insert(0, compaction)
    agent = build_agent(build_model(settings), [read_log, run_tests, apply_fix], middleware, B1_SYSTEM_PROMPT)

    mode = "COMPACT" if compact else "BASELINE (không compact)"
    print(f"\n{'=' * 78}\nB1 · {mode}\n{'=' * 78}")
    history: list = []
    for label, text in TURNS:
        history, _ = run_turn(agent, history, text, label, logger)
    extra = 0
    while compact and not compaction.events and extra < 3:  # đảm bảo compact đã chạy trước khi hỏi lại
        extra += 1
        history, _ = run_turn(agent, history, FILLER_TURN, f"T5+{extra}", logger)

    history, new = run_turn(agent, history, FINAL_QUESTION, "HỎI LẠI", logger)
    final_answer = message_text(new[-1]) if new else ""
    correct_before = STATE.correct_fixes
    history, new = run_turn(agent, history, CONTINUE_TURN, "LÀM TIẾP", logger)
    reran_tests = any(isinstance(m, AIMessage) and any(c["name"] == "run_tests" for c in m.tool_calls) for m in new)
    return {"mode": mode, "logger": logger, "compaction": compaction, "final_answer": final_answer,
            "fix_attempts": list(STATE.fix_attempts), "fixed_in_turn": STATE.correct_fixes > correct_before, "reran_tests": reran_tests}


def print_token_table(run: dict) -> None:
    logger = run["logger"]
    print(f"\nBẢNG TOKEN · {run['mode']} (số liệu `usage` do API trả về)")
    print(f"{'#':>3} {'lượt':<8} {'loại':<11} {'input_tokens':>12} {'output':>7} {'cache_hit':>9}  ghi chú")
    compacted = 0
    previous_kind = None
    for r in logger.records:
        note = ""
        if r["kind"] == "checkpoint":
            compacted += 1
            note = f"LLM tạo checkpoint (compact #{compacted})"
        elif previous_kind == "checkpoint":
            note = f"◄ lần gọi đầu SAU compact #{compacted}"
        previous_kind = r["kind"]
        cache = "-" if r["cache_hit"] is None else f"{r['cache_hit']:,}"
        print(f"{r['n']:>3} {r['turn']:<8} {r['kind']:<11} {r['input_tokens']:>12,} {r['output_tokens']:>7,} {cache:>9}  {note}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-baseline", action="store_true", help="bỏ lần chạy đối chứng không compact")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    settings, missing = load_settings()
    if not settings:
        print("Thiếu cấu hình trong .env:", ", ".join(missing))
        return 2

    console = sys.stdout
    with LOG_PATH.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(console, log)
        try:
            return run_all(settings, with_baseline=not args.no_baseline)
        finally:
            sys.stdout = console


def run_all(settings, with_baseline: bool) -> int:
    compact_run = run_session(settings, compact=True)
    runs = [compact_run]
    events = compact_run["compaction"].events
    # Ghi kết quả của lần chạy có compact ngay, để lần đối chứng có hỏng cũng không mất.
    compact_run["logger"].write_jsonl(paths.TRACES_DIR / "b1-compact.jsonl")
    (paths.TRACES_DIR / "b1-compaction-events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    if with_baseline:
        try:
            baseline_run = run_session(settings, compact=False)
        except Exception as exc:  # ví dụ context quá lớn so với giới hạn model: ghi lại thay vì mất kết quả compact
            print(f"\nLần đối chứng không compact bị dừng: {type(exc).__name__}: {str(exc)[:200]}")
        else:
            runs.append(baseline_run)
            baseline_run["logger"].write_jsonl(paths.TRACES_DIR / "b1-baseline.jsonl")
    with_baseline = len(runs) > 1

    banner = "=" * 78
    for run in runs:
        print(f"\n{banner}")
        print_token_table(run)

    print(f"\n{banner}\nSO SÁNH TỔNG TOKEN (mọi lần gọi model, gồm cả lần gọi tạo checkpoint)\n{banner}")
    print(f"{'chế độ':<26} {'số lần gọi':>10} {'input tổng':>12} {'input đỉnh':>11} {'output':>8} {'cache hit':>10}")
    for run in runs:
        t = run["logger"].totals()
        cache = "-" if t["cache_hit_total"] is None else f"{t['cache_hit_total']:,}"
        print(f"{run['mode']:<26} {t['calls']:>10} {t['input_total']:>12,} {t['input_peak']:>11,} {t['output_total']:>8,} {cache:>10}")
    if with_baseline and runs[1]["logger"].totals()["input_total"]:
        a, b = runs[0]["logger"].totals(), runs[1]["logger"].totals()
        print(f"Compact tốn {a['input_total'] / b['input_total']:.0%} input tokens của baseline "
              f"(đã tính {a['input_checkpoint']:,} input tokens của {a['checkpoint_calls']} lần tạo checkpoint). "
              "Hai lần chạy do model sinh nên số lần gọi tool có thể khác nhau chút.")

    if events:
        print(f"\n{banner}\nCHECKPOINT THẬT (lần compact cuối)\n{banner}")
        print(Checkpoint(**events[-1]["checkpoint"]).render())

    print(f"\n{banner}\nKIỂM CHỨNG (code chấm bằng keyword, không dựa vào lời agent tự khai)\n{banner}")
    all_ok = len(events) >= 1
    print(f"Compact kích hoạt ≥ 1 lần: {'PASS' if all_ok else 'FAIL'} ({len(events)} lần)")
    for run in runs:
        print(f"\n[{run['mode']}] câu trả lời sau compact:\n{run['final_answer']}")
        results = grade_final_answer(run["final_answer"])
        for name, ok, detail in results:
            print(f"  {name}: {'PASS' if ok else 'FAIL'} ({detail})")
        continued = run["fixed_in_turn"] and run["reran_tests"]
        print(f"  agent làm tiếp đúng task (áp fix đúng rồi chạy lại test): {'PASS' if continued else 'FAIL'} | fix đã áp: {run['fix_attempts']}")
        if run["compaction"] is not None:
            all_ok = all_ok and all(ok for _, ok, _ in results) and continued
            missing_fields = [e["missing_fields"] for e in run["compaction"].events if e["missing_fields"]]
            print(f"  checkpoint có trường rỗng? {missing_fields or 'không'}")
        print(f"  (thông tin thêm) nhắc ràng buộc restart production: {'có' if 'restart' in fold(run['final_answer']) else 'không'}")
    print(f"\nKẾT QUẢ B1 (chỉ tính lần chạy có compact): {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
