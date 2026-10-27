"""B2: sinh 50 file log giả có ground truth để so Native tool calling với Code Mode.

    python fixtures/make_logs.py

Ghi workspace/logs/service-01.log ... service-50.log (mỗi file ~200-260 dòng, seed cố định nên lần nào cũng giống nhau)
và fixtures/ground_truth.json (đếm bằng cách PARSE lại chính các dòng đã ghi, không dựa vào sổ sách lúc sinh).
Đáp án để NGOÀI workspace, agent không đọc được qua read_file.

Bẫy cố ý: nhiều dòng WARN nhắc đúng tên lỗi ("retrying after TimeoutError ...") nên đếm thô bằng grep tên lỗi sẽ ra số quá cao;
đề bài chỉ tính dòng mức ERROR.
"""

from __future__ import annotations

import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

SEED = 373
N_FILES = 50
HOT_FILE = 37  # file được thêm lỗi phổ biến nhất để "file có nhiều nhất" là duy nhất
HOT_EXTRA_ERRORS = 9

# Tên lỗi và trọng số (cách xa nhau để lỗi phổ biến nhất là duy nhất, kiểm lại bằng assert ở cuối).
ERRORS = {
    "TimeoutError": 34,
    "ConnectionResetError": 25,
    "DBPoolExhaustedError": 17,
    "AuthTokenExpired": 11,
    "ValidationError": 8,
    "DiskQuotaExceeded": 5,
}
_ERROR_LINE = re.compile(r"^\S+ \S+ ERROR \[(?P<svc>[^\]]+)\] (?P<name>\w+):")


def error_message(name: str, rng: random.Random) -> str:
    return {
        "TimeoutError": f"upstream call exceeded {rng.choice([3000, 5000, 8000])}ms",
        "ConnectionResetError": "peer closed connection (errno 104)",
        "DBPoolExhaustedError": "connection pool exhausted (active=20/20)",
        "AuthTokenExpired": f"token expired for user u-{rng.randint(100, 999)}",
        "ValidationError": f"invalid field '{rng.choice(['email', 'amount', 'currency', 'zip'])}'",
        "DiskQuotaExceeded": f"volume /data at {rng.randint(91, 99)}% capacity",
    }[name]


def make_file(index: int, rng: random.Random, error_names: list[str]) -> str:
    svc = f"service-{index:02d}"
    n_lines = rng.randint(200, 260)
    t = datetime(2026, 10, 26, 8, 0, 0)
    lines = []
    for _ in range(n_lines):
        t += timedelta(milliseconds=rng.randint(200, 4000))
        stamp = t.strftime("%Y-%m-%d %H:%M:%S")
        roll = rng.random()
        if roll < 0.80:
            lines.append(f"{stamp} INFO  [{svc}] {rng.choice(['GET', 'POST'])} {rng.choice(['/api/orders', '/api/cart', '/api/users', '/api/items'])} "
                         f"{rng.choice([200, 200, 200, 201, 204])} {rng.randint(8, 480)}ms request_id=r-{rng.randint(10000, 99999)}")
        elif roll < 0.92:  # decoy: WARN nhắc tên lỗi nhưng không phải dòng ERROR
            lines.append(f"{stamp} WARN  [{svc}] retrying after {rng.choice(list(ERRORS))} (attempt {rng.randint(1, 3)}/3)")
        else:
            lines.append(f"{stamp} WARN  [{svc}] slow response {rng.randint(900, 2500)}ms")
    # thay dòng ở vị trí ngẫu nhiên bằng dòng ERROR
    for pos in rng.sample(range(n_lines), len(error_names)):
        stamp = lines[pos][:19]
        name = error_names.pop()
        lines[pos] = f"{stamp} ERROR [{svc}] {name}: {error_message(name, rng)} request_id=r-{rng.randint(10000, 99999)}"
    return "\n".join(lines) + "\n"


def main() -> None:
    rng = random.Random(SEED)
    top_error = max(ERRORS, key=ERRORS.get)
    paths.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    for old in paths.LOGS_DIR.glob("service-*.log"):
        old.unlink()
    total_lines = total_chars = 0
    for index in range(1, N_FILES + 1):
        names = rng.choices(list(ERRORS), weights=list(ERRORS.values()), k=rng.randint(6, 14))
        if index == HOT_FILE:
            names += [top_error] * HOT_EXTRA_ERRORS
        text = make_file(index, rng, names)
        (paths.LOGS_DIR / f"service-{index:02d}.log").write_text(text, encoding="utf-8")
        total_lines += text.count("\n")
        total_chars += len(text)

    per_file: dict[str, dict[str, int]] = {}
    for path in sorted(paths.LOGS_DIR.glob("service-*.log")):
        counts: dict[str, int] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _ERROR_LINE.match(line)
            if match:
                counts[match["name"]] = counts.get(match["name"], 0) + 1
        per_file[path.name] = counts
    totals: dict[str, int] = {}
    for counts in per_file.values():
        for name, n in counts.items():
            totals[name] = totals.get(name, 0) + n

    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    assert ranked[0][1] > ranked[1][1], f"lỗi phổ biến nhất phải duy nhất: {ranked[:2]}"
    top_name, top_total = ranked[0]
    by_file = sorted(((counts.get(top_name, 0), name) for name, counts in per_file.items()), reverse=True)
    assert by_file[0][0] > by_file[1][0], f"file có nhiều lỗi đó nhất phải duy nhất: {by_file[:2]}"

    truth = {
        "seed": SEED, "n_files": N_FILES, "total_lines": total_lines, "total_chars": total_chars,
        "error_totals": dict(ranked),
        "top_error": {"name": top_name, "total": top_total},
        "top_file_for_top_error": {"file": by_file[0][1], "count": by_file[0][0]},
        "per_file": per_file,  # demo dùng để tính đáp án cho tập con N file đầu
    }
    paths.GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    paths.GROUND_TRUTH_PATH.write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã sinh {N_FILES} file ({total_lines:,} dòng, {total_chars:,} ký tự) trong {paths.LOGS_DIR}")
    print(f"Ground truth: lỗi nhiều nhất = {top_name} ({top_total} lần), file nhiều nhất = {by_file[0][1]} ({by_file[0][0]} lần)")
    print(f"Tổng theo lỗi: {dict(ranked)}")


if __name__ == "__main__":
    main()
