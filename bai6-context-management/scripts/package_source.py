"""Đóng gói zip nộp bài: toàn bộ project trừ .env, .venv, cache, bản raw archive và file bàn giao nội bộ.

    python scripts/package_source.py

Kiểm lại sau khi nén: zip không chứa .env/.git, và không chứa giá trị API key đang dùng (nếu có .env để so).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
# Đặt tên theo cách đã nộp Challenge A (Nhom15_ChallengeA.zip, thư mục gốc cùng tên trong zip).
PACKAGE_NAME = "Nhom15_ChallengeB"
OUTPUT = ROOT / "output" / f"{PACKAGE_NAME}.zip"
REPORT_PDF = ROOT / "BAO_CAO.pdf"  # báo cáo nộp riêng; bản này cũng nằm trong zip
EXCLUDED_PARTS = {".git", ".venv", ".claude", "__pycache__", ".pytest_cache", "output", "archive"}
EXCLUDED_NAMES = {".env", "HANDOVER.md"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return not (
        any(part in EXCLUDED_PARTS for part in relative.parts)
        or path.name in EXCLUDED_NAMES
        or path.suffix in {".pyc", ".pyo"}
    )


def secret_values() -> list[bytes]:
    """Các giá trị khoá đang dùng (từ .env và biến môi trường) để chắc chắn không lọt vào zip."""
    values = {v for k, v in dotenv_values(ROOT / ".env").items() if v and "KEY" in k.upper()}
    values |= {v for k, v in os.environ.items() if v and "API_KEY" in k.upper()}
    return [v.encode("utf-8") for v in values if len(v) >= 8]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file() and should_include(path):
                archive.write(path, Path(PACKAGE_NAME) / path.relative_to(ROOT))
    secrets = secret_values()
    with ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        bad = [n for n in names if n.endswith("/.env") or "/.git/" in n or "/.venv/" in n]
        if bad:
            raise RuntimeError(f"ZIP chứa file bị cấm: {bad}")
        for name in names:
            content = archive.read(name)
            if any(secret in content for secret in secrets):
                raise RuntimeError(f"ZIP chứa giá trị API key trong file: {name}")
    print(f"{OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB, {len(names)} file, đã kiểm: không .env, không API key)")
    if REPORT_PDF.exists():
        report_copy = OUTPUT.parent / f"{PACKAGE_NAME}_BaoCao.pdf"
        shutil.copy2(REPORT_PDF, report_copy)
        print(f"{report_copy} (báo cáo PDF nộp kèm zip)")
    else:
        print("Chưa có BAO_CAO.pdf: chạy python scripts/build_report_pdf.py trước")


if __name__ == "__main__":
    main()
