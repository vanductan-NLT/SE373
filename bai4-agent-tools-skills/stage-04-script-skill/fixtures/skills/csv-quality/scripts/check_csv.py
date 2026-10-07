#!/usr/bin/env python3
"""Kiểm tra chất lượng CSV công việc (task_id, owner, hours), tính tổng giờ theo người và xác định người quá tải.

Cách chạy (cwd là workspace):
    python skills/csv-quality/scripts/check_csv.py --input data/tasks.csv --max-hours 8

Exit 0: phân tích thành công, kể cả khi dữ liệu có lỗi chất lượng hoặc có người quá tải.
Exit khác 0: file không tồn tại/không đọc được, thiếu cột bắt buộc, lỗi parse CSV, thiếu hoặc sai --max-hours; thông báo ra stderr.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys

REQUIRED_COLUMNS = ("task_id", "owner", "hours")


class InputError(Exception):
    pass


def parse_hours(raw: str | None) -> float | None:
    """Số giờ hợp lệ: số hữu hạn, không âm. Trả None nếu không hợp lệ."""
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def parse_max_hours(raw: str | None) -> float:
    """Phân tích và kiểm tra giá trị max-hours. Bắt buộc là số hữu hạn không âm."""
    if raw is None or not str(raw).strip():
        raise InputError("Thiếu tham số --max-hours.")
    try:
        val = float(str(raw).strip())
    except ValueError:
        raise InputError(f"--max-hours '{raw}' không phải là số hợp lệ.")
    if not math.isfinite(val) or val < 0:
        raise InputError(f"--max-hours '{raw}' phải là số hữu hạn không âm.")
    return val


def format_num(val: float) -> int | float:
    """Định dạng số nguyên thành int để JSON gọn gàng, giữ float nếu có phần thập phân."""
    return int(val) if val.is_integer() else val


def analyze(path: str, max_hours: float) -> dict:
    try:
        handle = open(path, encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise InputError(f"Không đọc được file {path}: {exc.strerror or exc}") from exc

    with handle:
        reader = csv.reader(handle, strict=True)
        try:
            header = next(reader, None)
            if header is None:
                raise InputError(f"File {path} rỗng, không có header.")
            columns = [c.strip() for c in header]
            missing = [c for c in REQUIRED_COLUMNS if c not in columns]
            if missing:
                raise InputError(f"Thiếu cột bắt buộc: {', '.join(missing)}. Header hiện có: {', '.join(columns)}")
            index = {name: columns.index(name) for name in REQUIRED_COLUMNS}

            row_count = 0
            missing_owner = 0
            invalid_hours = 0
            first_seen: dict[str, int] = {}
            duplicate_ids: list[str] = []
            issues: list[dict] = []

            hours_by_owner: dict[str, float] = {}
            excluded_rows: list[dict] = []

            for row in reader:
                line = reader.line_num
                if not any(cell.strip() for cell in row):
                    continue  # bỏ qua dòng trống
                row_count += 1

                def cell(name: str) -> str:
                    position = index[name]
                    return row[position].strip() if position < len(row) else ""

                task_id, owner, hours_str = cell("task_id"), cell("owner"), cell("hours")
                reasons: list[str] = []

                # 1. wrong_field_count
                if len(row) != len(columns):
                    reasons.append("wrong_field_count")
                    issues.append({
                        "line": line, "column": None, "type": "wrong_field_count",
                        "task_id": task_id or None,
                        "message": f"Có {len(row)} trường, header có {len(columns)} cột."
                    })

                # 2. missing_task_id
                if not task_id:
                    reasons.append("missing_task_id")
                    issues.append({
                        "line": line, "column": "task_id", "type": "missing_task_id",
                        "task_id": None, "message": "task_id trống."
                    })
                # 3. duplicate_id
                elif task_id in first_seen:
                    if task_id not in duplicate_ids:
                        duplicate_ids.append(task_id)
                    reasons.append("duplicate_id")
                    issues.append({
                        "line": line, "column": "task_id", "type": "duplicate_id",
                        "task_id": task_id,
                        "message": f"task_id {task_id} đã xuất hiện ở line {first_seen[task_id]}."
                    })
                else:
                    first_seen[task_id] = line

                # 4. missing_owner
                if not owner:
                    missing_owner += 1
                    reasons.append("missing_owner")
                    issues.append({
                        "line": line, "column": "owner", "type": "missing_owner",
                        "task_id": task_id or None, "message": "owner trống."
                    })

                # 5. invalid_hours
                parsed_h = parse_hours(hours_str)
                if parsed_h is None:
                    invalid_hours += 1
                    reasons.append("invalid_hours")
                    issues.append({
                        "line": line, "column": "hours", "type": "invalid_hours",
                        "task_id": task_id or None, "value": hours_str,
                        "message": f"hours '{hours_str}' không phải số hữu hạn không âm."
                    })

                # Kiểm tra đủ điều kiện cộng tổng giờ
                if not reasons:
                    hours_by_owner[owner] = hours_by_owner.get(owner, 0.0) + parsed_h
                else:
                    excluded_rows.append({
                        "line": line,
                        "task_id": task_id or None,
                        "reasons": reasons
                    })

        except csv.Error as exc:
            raise InputError(f"Lỗi parse CSV ở line {reader.line_num}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise InputError(f"File {path} không phải UTF-8: {exc}") from exc

    # Xác định người quá tải (total_hours > max_hours), sắp xếp theo tên
    overloaded_owners = []
    for owner in sorted(hours_by_owner.keys()):
        tot = hours_by_owner[owner]
        if tot > max_hours:
            overloaded_owners.append({
                "owner": owner,
                "total_hours": format_num(tot)
            })

    formatted_hours_by_owner = {
        owner: format_num(tot) for owner, tot in hours_by_owner.items()
    }

    return {
        "input": path,
        "max_hours": format_num(max_hours),
        "row_count": row_count,
        "missing_owner_count": missing_owner,
        "invalid_hours_count": invalid_hours,
        "duplicate_id_count": len(duplicate_ids),
        "duplicate_ids": duplicate_ids,
        "hours_by_owner": formatted_hours_by_owner,
        "overloaded_owners": overloaded_owners,
        "excluded_rows": sorted(excluded_rows, key=lambda item: item["line"]),
        "issues": sorted(issues, key=lambda item: item["line"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kiểm tra chất lượng CSV công việc (task_id, owner, hours).")
    parser.add_argument("--input", required=True, help="Đường dẫn CSV, ví dụ data/tasks.csv")
    parser.add_argument("--max-hours", required=False, default=None, help="Ngưỡng giờ tối đa (số hữu hạn không âm)")
    args = parser.parse_args(argv)

    if args.max_hours is None:
        print("ERROR: Thiếu tham số bắt buộc --max-hours.", file=sys.stderr)
        return 2

    try:
        max_h = parse_max_hours(args.max_hours)
        result = analyze(args.input, max_h)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
