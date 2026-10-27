"""Ghi mỗi lần gọi model: input_tokens, output_tokens, cache hit → danh sách trong RAM + file JSONL.

Dùng như callback của LangChain: agent.invoke(..., config={"callbacks": [logger]}).
Số liệu lấy từ `usage` mà API trả về (không tự ước lượng), đúng gợi ý B2 "Đo input tokens qua usage".
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler


class TokenLogger(BaseCallbackHandler):
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.turn = 0  # demo gán số lượt user hiện tại để bảng có cột "lượt"
        self.tool_calls = 0  # số lần chạy tool (đếm được cả khi phiên chết giữa chừng vì tràn context)
        self.tool_output_chars = 0  # tổng ký tự tool output đã quay về cho model: thước đo "raw log có vào context không"
        self._seen: set = set()  # một lần gọi model chỉ ghi một lần, dù callback đi theo đường nào

    def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        self.tool_calls += 1

    def on_tool_end(self, output, **kwargs) -> None:
        self.tool_output_chars += len(str(getattr(output, "content", output)))

    def on_llm_end(self, response, *, run_id, tags=None, **kwargs) -> None:
        if run_id in self._seen:
            return
        self._seen.add(run_id)
        message = response.generations[0][0].message
        usage = getattr(message, "usage_metadata", None) or {}
        details = usage.get("input_token_details") or {}
        cache_hit = details.get("cache_read")
        if cache_hit is None:  # DeepSeek có thể trả cache hit ở token_usage thay vì input_token_details
            token_usage = (getattr(message, "response_metadata", None) or {}).get("token_usage") or {}
            cache_hit = token_usage.get("prompt_cache_hit_tokens")
        self.records.append({
            "n": len(self.records) + 1,
            "turn": self.turn,
            "kind": "checkpoint" if "checkpoint" in (tags or []) else "agent",
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_hit": cache_hit,
        })

    def totals(self) -> dict:
        """Tổng hợp: số lần gọi, tổng/đỉnh input_tokens, tổng output_tokens, tổng cache hit (nếu API có trả)."""
        agent = [r for r in self.records if r["kind"] == "agent"]
        ckpt = [r for r in self.records if r["kind"] == "checkpoint"]
        hits = [r["cache_hit"] for r in self.records if r["cache_hit"] is not None]
        return {
            "calls": len(self.records),
            "agent_calls": len(agent),
            "checkpoint_calls": len(ckpt),
            "input_total": sum(r["input_tokens"] for r in self.records),
            "input_agent": sum(r["input_tokens"] for r in agent),
            "input_checkpoint": sum(r["input_tokens"] for r in ckpt),
            "input_peak": max((r["input_tokens"] for r in self.records), default=0),
            "output_total": sum(r["output_tokens"] for r in self.records),
            "cache_hit_total": sum(hits) if hits else None,
        }

    def write_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for record in self.records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
