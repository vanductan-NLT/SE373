"""Versioned prompt templates with instructions separated from input."""

from __future__ import annotations

import json
from .models import IssueTriage

CLASSIFICATION_SYSTEM_PROMPT = """Bạn là kỹ sư trực vận hành phân loại issue phần mềm.
Rubric: P0 là outage diện rộng/mất dữ liệu/bảo mật nghiêm trọng; P1 là lỗi chức
năng quan trọng với phạm vi lớn; P2 là lỗi hạn chế hoặc có workaround; P3 là lỗi
nhỏ/cosmetic không chặn người dùng.
Không suy đoán. Dùng insufficient_data nếu thiếu symptom hoặc phạm vi ảnh hưởng;
dùng out_of_scope nếu không phải issue phần mềm. Với classified, severity bắt
buộc và needs_urgent_response=true chỉ cho P0/P1. Với status khác, severity=null
và needs_urgent_response=false. component là tên kỹ thuật ngắn, chữ thường hoặc
null. Chỉ trả JSON object có đúng status, severity, component,
needs_urgent_response, reason; không thêm prose/code fence."""

TOOL_SYSTEM_PROMPT = """Issue đã được application validate. Hãy gọi
get_component_owner đúng một lần với component được cung cấp. Không tự bịa owner
và không trả lời thay cho tool."""

FINAL_SYSTEM_PROMPT = """Viết kết luận triage ngắn bằng tiếng Việt chỉ dựa trên
IssueTriage và tool result đã cung cấp. Nêu severity, component, team và lý do;
không thay đổi dữ liệu."""


def classification_messages(issue: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"<issue_text>\n{issue}\n</issue_text>"},
    ]


def tool_messages(issue: str, triage: IssueTriage) -> list[dict[str, str]]:
    payload = json.dumps(triage.model_dump(), ensure_ascii=False)
    return [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
        {"role": "user", "content": f"Issue gốc:\n{issue}\n\nIssueTriage đã validate:\n{payload}"},
    ]
