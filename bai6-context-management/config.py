"""Cấu hình project: ngưỡng compact, giới hạn thực thi và settings đọc từ .env."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

import paths

# --- Giới hạn vòng lặp agent (mỗi lần agent.invoke = một lượt user) ---
# Giới hạn số lần gọi model trong một lượt (ModelCallLimitMiddleware).
MODEL_CALL_LIMIT = 10
# Giới hạn số tool calls trong một lượt (ToolCallLimitMiddleware).
TOOL_CALL_LIMIT = 20
# Giới hạn số bước của LangGraph (recursion limit), không phải số tool calls.
RECURSION_LIMIT = 80

# --- B1: Compact ---
# Ngưỡng kích hoạt compact (token). Cố ý để NHỎ để demo chắc chắn kích hoạt.
# Thực tế nên đặt khoảng 60-70% context window của model (slide 25: không đợi đầy mới compact).
COMPACT_TRIGGER_TOKENS = 20_000
# Số message gần nhất giữ nguyên (tính từ cuối); điểm cắt thật được lùi về ranh giới an toàn.
COMPACT_KEEP_LAST_MESSAGES = 4
# ToolMessage dài hơn ngưỡng này (ký tự) thì bị rút gọn (giữ dòng lỗi, gộp dòng lặp).
PRUNE_MIN_CHARS = 1_500
# Số dòng lỗi/FAIL (đã gộp trùng) giữ lại tối đa trong một tool output đã rút gọn.
PRUNE_MAX_KEY_LINES = 25

# --- B2: Code Mode ---
RUN_PYTHON_TIMEOUT_SECONDS = 15
MAX_OUTPUT_CHARS = 2_000
# Chế độ native phải đọc hàng chục file nên cần trần cao hơn; tràn trần cũng là một kết quả để ghi lại.
NATIVE_MODEL_CALL_LIMIT = 80
NATIVE_TOOL_CALL_LIMIT = 150


@dataclass(frozen=True)
class Settings:
    api_key: str
    model_name: str
    base_url: str | None


def load_settings() -> tuple[Settings | None, list[str]]:
    """Đọc .env của project này. Trả (settings, []) hoặc (None, danh sách biến còn thiếu)."""
    load_dotenv(paths.ENV_PATH, override=False)
    api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
    model_name = (os.getenv("MODEL_NAME") or os.getenv("DEEPSEEK_MODEL") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or "").strip() or None
    if not base_url and os.getenv("DEEPSEEK_API_KEY"):
        base_url = "https://api.deepseek.com"
    if not model_name and os.getenv("DEEPSEEK_API_KEY"):
        model_name = "deepseek-chat"
    missing = [name for name, value in (("OPENAI_API_KEY hoặc DEEPSEEK_API_KEY", api_key), ("MODEL_NAME hoặc DEEPSEEK_MODEL", model_name)) if not value]
    if missing:
        return None, missing
    return Settings(api_key=api_key, model_name=model_name, base_url=base_url), []
