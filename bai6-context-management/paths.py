"""Đường dẫn của project, resolve từ vị trí file này (không phụ thuộc thư mục terminal)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"
TRACES_DIR = PROJECT_ROOT / "traces"
ARCHIVE_DIR = TRACES_DIR / "archive"  # bản raw của tool output đã bị rút gọn (B1)
FIXTURES_DIR = PROJECT_ROOT / "fixtures"
GROUND_TRUTH_PATH = FIXTURES_DIR / "ground_truth.json"  # đáp án B2, để NGOÀI workspace nên read_file không đọc được (run_python không phải sandbox nên về lý thuyết vẫn đọc được)
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
LOGS_DIR = WORKSPACE_DIR / "logs"  # 50 file log của B2
OUTPUT_SUBDIR = "output"
