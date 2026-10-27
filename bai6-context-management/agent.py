"""Dựng agent cho bài 6: LangChain v1 create_agent + ChatOpenAI trỏ DeepSeek.

Mỗi demo tự chọn tools, middleware và system prompt: B1 dùng debug_tools + CompactionMiddleware,
B2 dùng files (native) hoặc run_python (Code Mode).
create_agent gắn lại system_prompt vào MỖI lần gọi model, nên system prompt không nằm trong messages
và không bị compact mất (slide 26: bước "reinject rules" chỉ cần lo phần ràng buộc do user nói giữa chat).
"""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from config import Settings


def build_model(settings: Settings, *, thinking: bool = True) -> ChatOpenAI:
    """thinking=False tắt chế độ suy luận của DeepSeek. Cần cho lời gọi structured output (checkpoint):
    ở thinking mode API từ chối ép tool_choice ("Thinking mode does not support this tool_choice")."""
    kwargs = {"model": settings.model_name, "api_key": settings.api_key, "temperature": 0}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    if not thinking and "deepseek" in (settings.base_url or ""):
        kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    return ChatOpenAI(**kwargs)


def build_agent(model, tools: list, middleware: list, system_prompt: str):
    return create_agent(model=model, tools=tools, system_prompt=system_prompt, middleware=middleware)
