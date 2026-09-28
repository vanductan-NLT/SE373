"""Environment configuration and DeepSeek client creation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
        if not api_key or api_key == "your_deepseek_api_key_here":
            raise ConfigurationError(
                "Thiếu DEEPSEEK_API_KEY. Hãy sao chép .env.example thành .env và điền API key thật."
            )
        return cls(
            api_key=api_key,
            base_url=(os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/"),
            model=(os.getenv("DEEPSEEK_MODEL") or "deepseek-flash").strip(),
        )

    def create_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)
