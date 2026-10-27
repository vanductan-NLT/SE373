"""B2 Code Mode: tool run_python(code).

Code chạy Ở ĐÂU: trong một tiến trình Python riêng (subprocess) do HARNESS (chương trình của chúng ta) khởi chạy.
LLM không tự chạy gì cả: nó chỉ viết mã (tool call run_python kèm chương trình), harness chạy, và LLM chỉ nhận
lại đúng những gì chương trình print ra (slide 28). Nhờ vậy 50 file log được đọc ở runtime, raw log không vào context.

Giới hạn: cwd là workspace, timeout, env tối thiểu (không truyền API key), output bị cắt ở MAX_OUTPUT_CHARS.
KHÔNG phải sandbox bảo mật (slide 31): chương trình vẫn đọc/ghi được ngoài workspace với quyền của user đang chạy.
Chỉ dùng trong môi trường lab với dữ liệu giả. Production cần sandbox thật, permission check và resource limit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool

import paths
from config import MAX_OUTPUT_CHARS, RUN_PYTHON_TIMEOUT_SECONDS


def minimal_env() -> dict[str, str]:
    """Env tối thiểu cho tiến trình con. Không truyền API key hay biến môi trường khác của process cha."""
    return {
        "PATH": str(Path(sys.executable).parent),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),  # Windows cần biến này để Python khởi động
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _clip(text: str) -> tuple[str, bool]:
    """Cắt output quá dài, kèm dòng báo tổng độ dài để LLM biết dữ liệu bị thiếu."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS] + f"\n…[đã cắt, tổng {len(text)} ký tự]", True


def _decode(value) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")


def _run_python(code: str, workspace: Path, timeout: float = RUN_PYTHON_TIMEOUT_SECONDS) -> dict:
    if not code.strip():
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": "", "timed_out": False,
                "error": {"code": "EMPTY_CODE", "message": "Chương trình rỗng."}}
    try:
        done = subprocess.run(
            [sys.executable, "-c", code],  # chạy thẳng interpreter, không qua shell (tránh lỗi Git Bash/WSL trên Windows)
            cwd=workspace, env=minimal_env(), stdin=subprocess.DEVNULL, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # subprocess.run đã kill tiến trình con
        stdout, out_clipped = _clip(_decode(exc.stdout))
        stderr, err_clipped = _clip(_decode(exc.stderr))
        return {"ok": False, "exit_code": None, "stdout": stdout, "stderr": stderr, "timed_out": True,
                "truncated": out_clipped or err_clipped,
                "error": {"code": "TIMEOUT", "message": f"Chương trình chạy quá {timeout} giây, đã dừng. stdout/stderr là phần đã có."}}
    stdout, out_clipped = _clip(done.stdout)
    stderr, err_clipped = _clip(done.stderr)
    return {"ok": True, "exit_code": done.returncode, "stdout": stdout, "stderr": stderr, "timed_out": False,
            "truncated": out_clipped or err_clipped}


@tool
def run_python(code: str) -> str:
    """Chạy một chương trình Python trong thư mục workspace và trả về JSON chứa những gì chương trình print ra.

    Dùng để đọc và xử lý nhiều file (ví dụ các file trong logs/) ngay trong chương trình thay vì đọc từng file qua tool.
    Chỉ print KẾT QUẢ CUỐI đã tổng hợp (vài dòng), không print raw dữ liệu: output quá 2000 ký tự bị cắt.
    Timeout 15 giây; đường dẫn tương đối workspace, ví dụ logs/service-01.log. Chương trình không được truyền API key.
    Đây KHÔNG phải sandbox bảo mật.
    Kết quả: {"ok": true, "exit_code": 0, "stdout": "...", "stderr": "", "timed_out": false, "truncated": false}.
    exit_code khác 0 nghĩa là chương trình báo lỗi (xem stderr). Timeout: {"ok": false, "timed_out": true, ...}.
    """
    return json.dumps(_run_python(code, paths.WORKSPACE_DIR), ensure_ascii=False)
