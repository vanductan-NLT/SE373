"""Agent của bài 5: agent stage-01-files (bài 4) cộng persistent memory.

Khác stage-01: build_agent nạp memory vào system prompt mỗi lần mở session và có thêm tool remember_convention.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_openai import ChatOpenAI

import memory_store
from config import MODEL_CALL_LIMIT, TOOL_CALL_LIMIT, Settings
from prompts import build_system_prompt
from tools import list_files, read_file, remember_convention, set_session, write_file

TOOLS = [read_file, write_file, list_files, remember_convention]


def build_model(settings: Settings) -> ChatOpenAI:
    kwargs = {"model": settings.model_name, "api_key": settings.api_key}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return ChatOpenAI(**kwargs)


def build_agent(model, session_id: str):
    """Mở một session mới: history rỗng, nhưng system prompt mang theo memory đã lưu trên đĩa."""
    set_session(session_id)
    memory_text = memory_store.render_for_context()
    agent = create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=build_system_prompt(memory_text),
        middleware=[
            ModelCallLimitMiddleware(run_limit=MODEL_CALL_LIMIT, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=TOOL_CALL_LIMIT),
        ],
    )
    return agent, memory_text
