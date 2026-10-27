"""Tools debug GIẢ cho B1: read_log, run_tests, apply_fix.

Kịch bản: "API POST /checkout thỉnh thoảng trả HTTP 500". Dữ liệu sinh deterministic (random.Random(seed)),
chạy lần nào cũng ra đúng cùng nội dung, nên demo lặp lại được. Mục đích là tạo tool output LỚN và NHIỄU
(đúng cảnh slide 19: log lặp, test output dài) để có cái mà compact.

Sự thật (ground truth) của kịch bản, chỉ log/test hé lộ dần:
  - Nguyên nhân: payment_client.charge() giữ kết nối DB suốt lúc chờ payment gateway chậm (8-12 giây)
    → pool DB (20 kết nối) cạn → /checkout trả 500 với DBPoolExhaustedError.
  - Fix sai (tăng timeout / tăng pool size / retry / restart): test vẫn fail.
  - Fix đúng: giải phóng kết nối DB trước khi gọi gateway (release/close/context manager): test pass.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from langchain_core.tools import tool

SEED = 373
LOG_LINES = {"checkout-api.log": 380, "db-pool.log": 360, "payment-gateway.log": 340}
TESTS_PASSED = 200


@dataclass
class DebugState:
    """Trạng thái phiên debug giả: các fix đã áp dụng và fix đúng đã được áp dụng chưa."""

    fix_attempts: list[str] = field(default_factory=list)
    fixed: bool = False
    correct_fixes: int = 0  # số lần apply_fix được nhận là fix đúng (demo so trước/sau một lượt để biết lượt đó có áp fix đúng không)

    def reset(self) -> None:
        self.fix_attempts.clear()
        self.fixed = False
        self.correct_fixes = 0


STATE = DebugState()


def _timeline(rng: random.Random):
    t = datetime(2026, 10, 26, 13, 58, 0)
    while True:
        t += timedelta(milliseconds=rng.randint(150, 3500))
        yield t.strftime("%Y-%m-%d %H:%M:%S.") + f"{t.microsecond // 1000:03d}"


def _insert_errors(rng: random.Random, lines: list[str], *specs) -> None:
    """Thay dòng ở vị trí ngẫu nhiên (cố định theo seed) bằng dòng lỗi thật.

    Mỗi spec là (hàm tạo dòng lỗi từ timestamp, số dòng). Vị trí của mọi spec được chọn một lần nên không đè nhau.
    """
    positions = rng.sample(range(40, len(lines)), sum(count for _, count in specs))
    for make_error, count in specs:
        for pos in sorted(positions[:count]):
            lines[pos] = make_error(lines[pos][:23])  # 23 ký tự đầu là timestamp "YYYY-MM-DD HH:MM:SS.mmm"
        positions = positions[count:]


def _checkout_api_log(rng: random.Random) -> list[str]:
    ts, lines = _timeline(rng), []
    for _ in range(LOG_LINES["checkout-api.log"]):
        t, r = next(ts), rng.random()
        if r < 0.42:  # nhiễu lặp: ~42% dòng là "Retrying connection..."
            lines.append(f"{t} INFO  [checkout-api] Retrying connection to db (attempt {rng.randint(1, 5)}/5)...")
        elif r < 0.80:
            lines.append(f"{t} INFO  [checkout-api] POST /checkout 200 {rng.randint(90, 420)}ms request_id=r-{rng.randint(10000, 99999)}")
        elif r < 0.92:
            lines.append(f"{t} INFO  [checkout-api] GET /health 200 {rng.randint(1, 4)}ms")
        elif r < 0.97:
            lines.append(f"{t} INFO  [checkout-api] cache hit key=cart:{rng.randint(1000, 9999)}")
        else:  # WARN gây nhiễu, không phải lỗi gốc
            lines.append(f"{t} WARN  [checkout-api] slow query {rng.randint(900, 2100)}ms SELECT * FROM orders WHERE user_id=?")
    _insert_errors(
        rng, lines,
        (lambda t: f"{t} ERROR [checkout-api] POST /checkout 500 DBPoolExhaustedError: connection pool exhausted "
                   f"(active=20/20, waiting={rng.randint(3, 19)}) request_id=r-{rng.randint(10000, 99999)}", 14),
        (lambda t: f"{t} ERROR [checkout-api] POST /checkout 400 ValidationError: invalid coupon code request_id=r-{rng.randint(10000, 99999)}", 2),
    )
    return lines


def _db_pool_log(rng: random.Random) -> list[str]:
    ts, lines = _timeline(rng), []
    for _ in range(LOG_LINES["db-pool.log"]):
        t, r = next(ts), rng.random()
        if r < 0.50:
            lines.append(f"{t} INFO  [db-pool] stats active={rng.randint(6, 20)}/20 idle={rng.randint(0, 9)} waiting={rng.randint(0, 6)}")
        elif r < 0.72:
            lines.append(f"{t} INFO  [db-pool] connection recycled id=c-{rng.randint(100, 999)}")
        elif r < 0.88:
            lines.append(f"{t} INFO  [db-pool] checkout id=c-{rng.randint(100, 999)} by={rng.choice(['order_service.create', 'cart_service.load', 'user_repo.get'])}")
        else:  # bằng chứng: kết nối bị payment_client.charge giữ rất lâu
            lines.append(f"{t} WARN  [db-pool] connection c-{rng.randint(100, 999)} held by payment_client.charge for {rng.uniform(8, 13):.1f}s")
    _insert_errors(
        rng, lines,
        (lambda t: f"{t} ERROR [db-pool] QueuePool limit of size 20 overflow 0 reached, connection timed out, timeout=30 "
                   f"(waiting={rng.randint(3, 19)})", 12),
    )
    return lines


def _payment_gateway_log(rng: random.Random) -> list[str]:
    ts, lines = _timeline(rng), []
    for _ in range(LOG_LINES["payment-gateway.log"]):
        t, r = next(ts), rng.random()
        if r < 0.74:
            lines.append(f"{t} INFO  [payment-gateway] charge ok order=o-{rng.randint(1000, 9999)} latency={rng.randint(120, 480)}ms")
        elif r < 0.86:
            lines.append(f"{t} WARN  [payment-gateway] slow response latency={rng.randint(8000, 12500)}ms order=o-{rng.randint(1000, 9999)}")
        else:
            lines.append(f"{t} INFO  [payment-gateway] health ok region={rng.choice(['sg', 'hk', 'jp'])}")
    _insert_errors(
        rng, lines,
        (lambda t: f"{t} ERROR [payment-gateway] upstream timeout after 12000ms order=o-{rng.randint(1000, 9999)}", 5),
    )
    return lines


_BUILDERS = {"checkout-api.log": _checkout_api_log, "db-pool.log": _db_pool_log, "payment-gateway.log": _payment_gateway_log}


@tool
def read_log(name: str) -> str:
    """Đọc TOÀN BỘ một file log của hệ thống và trả về dạng text (mỗi dòng một sự kiện).

    name là tên file log, một trong: checkout-api.log, db-pool.log, payment-gateway.log.
    File dài hàng trăm dòng, có nhiều dòng INFO lặp lại; lỗi thật nằm lẫn trong đó (mức ERROR).
    """
    if name not in _BUILDERS:
        return f"Lỗi: không có file log '{name}'. Tên hợp lệ: {', '.join(sorted(_BUILDERS))}"
    lines = _BUILDERS[name](random.Random(f"{SEED}:{name}"))
    return f"== {name} ({len(lines)} dòng) ==\n" + "\n".join(lines)


_MODULES = ["cart", "catalog", "auth", "coupon", "shipping", "tax", "inventory", "orders", "payment", "checkout"]
_VERBS = ["add", "remove", "update", "validate", "apply", "calc", "list", "reject", "merge", "refund"]
_NOUNS = ["item", "coupon", "address", "total", "stock", "token", "discount", "tax", "shipment", "receipt"]

_TRACEBACK = """    resp = client.post("/checkout", json=payload)
app/api/checkout.py:57: in checkout
    order = order_service.create(cart, user)
app/services/order_service.py:41: in create
    with db.connection() as conn:
app/db/pool.py:112: in connection
    return self._pool.acquire(timeout=self.timeout)
app/db/pool.py:78: in acquire
    raise DBPoolExhaustedError(f"connection pool exhausted (active={self.active}/{self.size}, waiting={self.waiting})")"""


def _failure_block(test: str, file: str, line: int, error_line: str, rng: random.Random) -> list[str]:
    block = [f"____________________ {test} ____________________", "Traceback (most recent call last):", f"{file}:{line}: in {test}"]
    for _ in range(3):  # lặp khung traceback cho đủ ~30 dòng như test thật
        block += _TRACEBACK.splitlines()
        block.append(f"  [frame {rng.randint(100, 999)}] ...")
    block.append(f"E   {error_line}")
    return block


def _build_test_output(fixed: bool) -> str:
    rng = random.Random(f"{SEED}:tests")
    out = ["============================= test session starts =============================", "platform win32 -- Python 3.13, pytest-8.3", f"collected {TESTS_PASSED + 3} items", ""]
    for i in range(TESTS_PASSED + 3):
        if i % 4 == 0:  # log khởi động lặp lại theo từng nhóm test
            out.append(f"2026-10-26 14:10:{i % 60:02d} INFO  [startup] app init env=test worker=gw0 loading config...")
        name = f"tests/test_{rng.choice(_MODULES)}.py::test_{rng.choice(_VERBS)}_{rng.choice(_NOUNS)}_{i}"
        out.append(f"{name} PASSED{' ' * 20}[{int((i + 1) * 100 / (TESTS_PASSED + 3)):3d}%]")
    if fixed:
        out.append(f"=================== {TESTS_PASSED + 3} passed in 11.82s ===================")
        return "\n".join(out)
    failures = [
        ("test_checkout_concurrent_orders", "tests/test_checkout.py", 88, "DBPoolExhaustedError: connection pool exhausted (active=20/20, waiting=14)"),
        ("test_checkout_burst_100_requests", "tests/test_checkout.py", 131, "DBPoolExhaustedError: connection pool exhausted (active=20/20, waiting=17)"),
        ("test_charge_releases_db_connection", "tests/test_payment.py", 54, "AssertionError: expected 0 DB connections held during gateway call, got 1"),
    ]
    out.append("=================================== FAILURES ===================================")
    for test, file, line, error in failures:
        out += _failure_block(test, file, line, error, rng)
    out.append("=========================== short test summary info ============================")
    for test, file, _, error in failures:
        out.append(f"FAILED {file}::{test} - {error}")
    out.append(f"=================== 3 failed, {TESTS_PASSED} passed in 11.82s ===================")
    return "\n".join(out)


@tool
def run_tests() -> str:
    """Chạy toàn bộ bộ test của dự án và trả về output đầy đủ dạng pytest -v (text).

    Output dài hàng trăm dòng: mỗi test một dòng PASSED/FAILED, log khởi động lặp, traceback của test lỗi,
    và dòng tổng kết ở cuối. Không có tham số.
    """
    return _build_test_output(STATE.fixed)


# Nhận ra "fix đúng" bằng từ khoá (kiểm tra thô): mô tả phải nói tới kết nối DB, tới lời gọi payment gateway, và có động từ
# giải phóng/thu hẹp phạm vi giữ kết nối. Bản đầu thiếu cách diễn đạt "trả về pool", "thu hẹp khối with" nên bỏ sót fix đúng.
# Cố ý không dùng từ ngắn dễ trùng như "trả", "dong".
_RELEASE_WORDS = ("release", "close", "đóng", "giải phóng", "giai phong", "trả lại", "trả kết nối", "trả về", "nhả", "thu hẹp",
                  "thoát khỏi", "thoát khối", "ngoài khối", "ngoài transaction", "leak", "rò rỉ", "context manager", "finally")
_TARGET_WORDS = ("connection", "kết nối", "ket noi", "pool")
_GATEWAY_WORDS = ("gateway", "payment", "charge", "thanh toán")


@tool
def apply_fix(description: str) -> str:
    """Áp dụng một thay đổi code để sửa lỗi. description mô tả CỤ THỂ thay đổi (sửa gì, ở đâu).

    Công cụ chỉ áp dụng thay đổi, KHÔNG tự chạy test: sau đó hãy gọi run_tests() để biết fix có hiệu quả không.
    """
    STATE.fix_attempts.append(description)
    text = description.lower()
    if all(any(w in text for w in words) for words in (_RELEASE_WORDS, _TARGET_WORDS, _GATEWAY_WORDS)):
        STATE.fixed = True
        STATE.correct_fixes += 1
    return f"Đã áp dụng thay đổi: {description}. Hãy chạy run_tests() để kiểm tra kết quả."
