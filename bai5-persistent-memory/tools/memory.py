"""Tool memory: agent gọi khi người dùng chốt hoặc đổi một quy ước dự án.

Agent chỉ đưa topic và rule. Việc thay thế dòng cũ do memory_store xử lý, không để LLM tự sửa file.
session_id do harness gán trước mỗi session để ghi nguồn gốc.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

import memory_store

_current_session = {"id": "session-?"}


def set_session(session_id: str) -> None:
    _current_session["id"] = session_id


@tool
def remember_convention(topic: str, rule: str) -> str:
    """Lưu một quy ước dự án vào memory dài hạn để các session sau còn dùng được.

    Chỉ gọi khi người dùng chốt hoặc ĐỔI một quy ước (tên file, định dạng, ngôn ngữ báo cáo...).
    topic: nhãn ngắn, ổn định, chữ thường, ví dụ report-format. Cùng topic với quy ước cũ thì quy ước cũ bị thay thế.
    rule: nội dung quy ước đầy đủ, tự đứng được, không cần ngữ cảnh hội thoại.
    Thành công: {"ok": true, "topic": ..., "status": "created" | "updated"}.
    """
    return json.dumps(memory_store.save_convention(topic, rule, _current_session["id"]), ensure_ascii=False)
