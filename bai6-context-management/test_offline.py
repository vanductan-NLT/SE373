"""Kiểm tra offline (KHÔNG gọi API): các hàm thuần của compact, debug tools và run_python.

    python test_offline.py

Dùng assert thường, không cần pytest. In "OK ..." cho từng nhóm; sai thì dừng ngay ở assert.
Trọng tâm là bẫy ToolMessage mồ côi: mọi điểm cắt có thể đều phải cho đuôi hợp lệ.
"""

from __future__ import annotations

import contextlib
import io
import os
import sys

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage

import paths
from compaction import (Checkpoint, CompactionMiddleware, estimate_tokens, find_cutoff, measure_context_tokens,
                        message_text, orphan_tool_messages)
from pruning import PRUNED_MARKER, prune_tool_output
from run_demo_b1 import grade_final_answer
from tools.code_mode import _clip, _run_python
from tools.debug_tools import STATE, apply_fix, read_log, run_tests


def make_session() -> list:
    """Một session có cả gọi tool đơn lẻ lẫn gọi 2 tool song song trong một AIMessage."""
    def call(name: str, call_id: str) -> dict:
        return {"name": name, "args": {}, "id": call_id}

    return [
        HumanMessage("lượt 1"),
        AIMessage("", tool_calls=[call("read_log", "c1")]), ToolMessage("log 1", tool_call_id="c1", name="read_log"),
        AIMessage("đã đọc"),
        HumanMessage("lượt 2"),
        AIMessage("", tool_calls=[call("run_tests", "c2"), call("read_log", "c3")]),
        ToolMessage("test", tool_call_id="c2", name="run_tests"), ToolMessage("log 2", tool_call_id="c3", name="read_log"),
        AIMessage("xong"),
        HumanMessage("lượt 3"),
        AIMessage("", tool_calls=[call("apply_fix", "c4")]), ToolMessage("ok", tool_call_id="c4", name="apply_fix"),
    ]


def test_cutoff_never_orphans_tool_messages() -> None:
    messages = make_session()
    assert not orphan_tool_messages(messages)
    for keep_last in range(1, len(messages) + 1):
        cutoff = find_cutoff(messages, keep_last)
        tail = messages[cutoff:]
        assert not orphan_tool_messages(tail), f"keep_last={keep_last} cutoff={cutoff}: đuôi có ToolMessage mồ côi"
    # cắt cứng giữa cặp AI/Tool (messages[6:] bắt đầu bằng ToolMessage) thì phải bị phát hiện
    assert orphan_tool_messages(messages[6:]) == ["c2", "c3"]
    print("OK find_cutoff: mọi điểm cắt cho đuôi hợp lệ; orphan_tool_messages bắt được cắt sai")


def test_measure_prefers_usage() -> None:
    ai = AIMessage("a", usage_metadata={"input_tokens": 9000, "output_tokens": 100, "total_tokens": 9100})
    messages = [HumanMessage("x" * 400), ai, ToolMessage("y" * 4000, tool_call_id="c", name="t")]
    tokens, source = measure_context_tokens(messages)
    assert source == "usage" and tokens == 9000 + 100 + 1000, (tokens, source)
    stripped = [messages[0], ai.model_copy(update={"usage_metadata": None}), messages[2]]
    tokens, source = measure_context_tokens(stripped)
    assert source == "ước lượng" and tokens == estimate_tokens(stripped)
    print("OK measure_context_tokens: ưu tiên usage thật, usage đã bỏ thì quay về ước lượng")


def test_prune_log_and_tests() -> None:
    raw = read_log.invoke({"name": "checkout-api.log"})
    pruned = prune_tool_output(raw, "traces/archive/x.txt")
    assert len(pruned) < len(raw) / 5, (len(pruned), len(raw))
    assert "(×14)" in pruned and "DBPoolExhaustedError" in pruned, "phải gộp 14 dòng 500 thành một nhóm có đếm"
    assert "ValidationError" in pruned and "Retrying connection" in pruned
    STATE.reset()
    raw_tests = run_tests.invoke({})
    pruned_tests = prune_tool_output(raw_tests, "traces/archive/y.txt")
    assert len(pruned_tests) < len(raw_tests) / 5
    assert pruned_tests.count("FAILED") == 3 and "3 failed, 200 passed" in pruned_tests
    print(f"OK prune: log {len(raw):,} → {len(pruned):,} ký tự; test {len(raw_tests):,} → {len(pruned_tests):,} ký tự, đủ 3 FAILED")


def test_debug_tools() -> None:
    assert read_log.invoke({"name": "db-pool.log"}) == read_log.invoke({"name": "db-pool.log"}), "phải deterministic"
    assert "Tên hợp lệ" in read_log.invoke({"name": "khong-co.log"})
    STATE.reset()
    apply_fix.invoke({"description": "tăng timeout kết nối DB lên 30 giây"})
    apply_fix.invoke({"description": "tăng pool size lên 50 kết nối"})
    apply_fix.invoke({"description": "đặt timeout gọi payment gateway là 5 giây"})
    assert not STATE.fixed and "3 failed" in run_tests.invoke({}), "fix sai thì test vẫn fail"
    apply_fix.invoke({"description": "thu hẹp khối with db.connection() để connection được trả về pool trước khi gọi payment gateway"})
    assert STATE.fixed, "cách diễn đạt khác của fix đúng cũng phải được nhận ra"
    STATE.reset()
    apply_fix.invoke({"description": "payment_client.charge() giải phóng kết nối DB (connection) trước khi gọi gateway"})
    assert STATE.fixed and "203 passed" in run_tests.invoke({}) and "FAILED" not in run_tests.invoke({})
    STATE.reset()
    print("OK debug_tools: deterministic; fix sai vẫn fail, fix đúng mới pass")


def test_run_python() -> None:
    paths.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["DEEPSEEK_API_KEY"] = "sk-test-khong-duoc-lot"
    out = _run_python("import os; print(os.environ.get('DEEPSEEK_API_KEY'))", paths.WORKSPACE_DIR)
    assert out["ok"] and out["stdout"].strip() == "None", "API key không được truyền vào tiến trình con"
    assert out["exit_code"] == 0
    err = _run_python("raise ValueError('x')", paths.WORKSPACE_DIR)
    assert err["exit_code"] != 0 and "ValueError" in err["stderr"]
    slow = _run_python("while True: pass", paths.WORKSPACE_DIR, timeout=1)
    assert slow["timed_out"] and not slow["ok"]
    big = _run_python("print('a' * 5000)", paths.WORKSPACE_DIR)
    assert big["truncated"] and "đã cắt, tổng" in big["stdout"]
    assert _clip("ngắn") == ("ngắn", False)
    print("OK run_python: không lộ API key, bắt lỗi, timeout, cắt output")


class FakeStructuredModel:
    """Thay LLM tạo checkpoint: trả lần lượt các kết quả (hoặc ném exception) đã định sẵn, đếm số lần được gọi."""

    def __init__(self, outcomes: list):
        self.outcomes, self.calls = list(outcomes), 0

    def with_structured_output(self, schema, method=None):
        return self

    def invoke(self, request, config=None):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def big_tool(call_id: str, name: str = "read_log") -> ToolMessage:
    return ToolMessage("== log ==\n" + "INFO lặp lại\n" * 400 + "ERROR DBPoolExhaustedError: pool cạn\n", tool_call_id=call_id, name=name)


def tool_ai(*call_ids: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": "read_log", "args": {}, "id": c} for c in call_ids])


def test_middleware_keeps_current_request_and_valid_tail() -> None:
    """Yêu cầu hiện tại của user nằm trong phần bị nén phải được ghi nguyên văn vào checkpoint; đuôi hợp lệ và đã rút gọn."""
    request = "YÊU CẦU HIỆN TẠI: làm bước X, đừng đổi API"
    messages = [HumanMessage("yêu cầu 1"), tool_ai("test_c1"), big_tool("test_c1"), AIMessage("xong 1"),
                HumanMessage(request), tool_ai("test_c2"), big_tool("test_c2"), tool_ai("test_c3"), big_tool("test_c3")]
    fake = FakeStructuredModel([Checkpoint(goal="g", current_state="s", constraints=["không đổi API"], findings=["f"], failed_attempts=["a"], files=["x"], next_action="n")])
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # middleware in banner compact, test chỉ cần kết quả
            update = CompactionMiddleware(fake, trigger_tokens=100, keep_last_messages=4).before_model({"messages": messages}, None)
    finally:
        for f in paths.ARCHIVE_DIR.glob("test_*.txt"):
            f.unlink()
    new = update["messages"]
    assert isinstance(new[0], RemoveMessage) and f"yêu cầu hiện tại của user (nguyên văn): {request}" in message_text(new[1])
    assert not orphan_tool_messages(new[1:]), "đuôi sau khi nén có ToolMessage mồ côi"
    assert [type(m).__name__ for m in new[2:]] == ["AIMessage", "ToolMessage", "AIMessage", "ToolMessage"]
    assert all(message_text(m).startswith(PRUNED_MARKER) for m in new[2:] if isinstance(m, ToolMessage)), "tool output dài ở đuôi phải được rút gọn"
    print("OK middleware: giữ nguyên văn yêu cầu hiện tại, đuôi hợp lệ, tool output đuôi được rút gọn")


def test_middleware_prunes_tail_when_head_is_only_checkpoint() -> None:
    """Đầu chỉ còn checkpoint cũ thì không gọi LLM, nhưng vẫn rút gọn tool output ở đuôi."""
    ckpt = HumanMessage("[CHECKPOINT] cũ", additional_kwargs={"compacted": True})
    messages = [ckpt, tool_ai("test_p1", "test_p2", "test_p3"), big_tool("test_p1"), big_tool("test_p2"), big_tool("test_p3")]
    fake = FakeStructuredModel([])  # bị gọi là ném IndexError
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            update = CompactionMiddleware(fake, trigger_tokens=100, keep_last_messages=4).before_model({"messages": messages}, None)
    finally:
        for f in paths.ARCHIVE_DIR.glob("test_*.txt"):
            f.unlink()
    assert fake.calls == 0 and update is not None
    new = update["messages"]
    assert isinstance(new[0], RemoveMessage) and new[1] is messages[0] and not orphan_tool_messages(new[1:])
    assert all(message_text(m).startswith(PRUNED_MARKER) for m in new if isinstance(m, ToolMessage))
    print("OK middleware: đầu chỉ có checkpoint cũ thì chỉ rút gọn đuôi, không gọi LLM")


def test_checkpoint_survives_missing_fields_and_bad_calls() -> None:
    partial = Checkpoint(goal="chỉ có mục tiêu")  # trước đây thiếu trường là ValidationError làm chết phiên
    assert partial.missing_fields() == ["current_state", "constraints", "findings", "failed_attempts", "files", "next_action"]
    fake = FakeStructuredModel([ValueError("args sai định dạng"), partial])
    middleware = CompactionMiddleware(fake, trigger_tokens=100)
    assert middleware._build_checkpoint([HumanMessage("x")]) is partial and fake.calls == 2, "lỗi lần 1 phải được thử lại"
    print("OK checkpoint: trường thiếu không làm chết phiên, lỗi tạo checkpoint được thử lại")


def test_grader_rejects_wrong_answers() -> None:
    right = ("(1) POST /checkout trả 500 do DBPoolExhaustedError. (2) Đã thử tăng timeout lên 30s: không cải thiện, test vẫn fail. "
             "(3) Ràng buộc: không đổi API công khai /checkout. (4) Bước tiếp: nhả connection DB về pool trước khi gọi payment gateway.")
    wrong = ("(1) POST /checkout trả 500. (2) Đã thử tăng timeout, rất hiệu quả, hết lỗi. (3) Không đổi API công khai /checkout. "
             "(4) Bước tiếp: tăng pool size và báo payment gateway.")
    assert all(ok for _, ok, _ in grade_final_answer(right))
    failed = [name for name, ok, _ in grade_final_answer(wrong) if not ok]
    assert failed == ["cách đã thử + kết quả", "bước tiếp theo hợp lý"], failed
    print("OK grader: câu đúng qua cả 4 ý; câu sai (timeout hiệu quả, tăng pool size) rớt đúng 2 ý")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    test_cutoff_never_orphans_tool_messages()
    test_measure_prefers_usage()
    test_prune_log_and_tests()
    test_debug_tools()
    test_run_python()
    test_middleware_keeps_current_request_and_valid_tail()
    test_middleware_prunes_tail_when_head_is_only_checkpoint()
    test_checkpoint_survives_missing_fields_and_bad_calls()
    test_grader_rejects_wrong_answers()
    print("TẤT CẢ OK")
