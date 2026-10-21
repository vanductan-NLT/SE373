"""Giao diện chat Streamlit cho agent bài 5 (persistent memory).

Chạy: .venv/Scripts/python.exe -m streamlit run app.py

Mỗi lần bấm "Mở session mới", history rỗng và memory được nạp lại từ memory/MEMORY.md.
Chat hiện đủ vòng lặp agent: model đề xuất tool, harness chạy tool, kết quả quay lại model.
"""

import json
import shutil

import streamlit as st
from langchain_core.messages import HumanMessage

import memory_store
import paths
from agent import build_agent, build_model
from config import RECURSION_LIMIT, load_settings

OUTPUT_DIR = paths.WORKSPACE_DIR / paths.OUTPUT_SUBDIR
MAX_SHOWN_CHARS = 600

st.set_page_config(page_title="Bài 5: Persistent memory", layout="wide")


@st.cache_resource
def get_model():
    settings, missing = load_settings()
    return (build_model(settings) if settings else None), missing


def clip(text: str) -> str:
    text = str(text)
    return text if len(text) <= MAX_SHOWN_CHARS else f"{text[:MAX_SHOWN_CHARS]}... (+{len(text) - MAX_SHOWN_CHARS} ký tự)"


def open_session() -> None:
    """Session mới: history rỗng, memory đọc từ đĩa và dán vào system prompt."""
    st.session_state.n_session = st.session_state.get("n_session", 0) + 1
    st.session_state.session_id = f"session-ui-{st.session_state.n_session}"
    st.session_state.agent, st.session_state.memory_text = build_agent(model, st.session_state.session_id)
    st.session_state.history = []


def render_message(m) -> None:
    if m.type == "human":
        with st.chat_message("user"):
            st.markdown(m.content)
    elif m.type == "ai":
        tokens = (m.usage_metadata or {}).get("input_tokens", "?")
        if m.tool_calls:
            with st.chat_message("assistant", avatar="🧠"):
                st.caption(f"Model đề xuất gọi tool (gửi {tokens} token input, gồm cả history)")
                for call in m.tool_calls:
                    st.code(f"{call['name']}({clip(json.dumps(call['args'], ensure_ascii=False))})", language="python", wrap_lines=True)
        else:
            with st.chat_message("assistant"):
                st.markdown(m.content)
                st.caption(f"Model trả lời cuối, không còn tool call nên vòng lặp dừng (gửi {tokens} token input)")
    elif m.type == "tool":
        with st.chat_message("assistant", avatar="⚙️"):
            st.caption(f"Harness (chương trình) đã chạy tool `{m.name}`, kết quả đưa lại cho model")
            st.code(clip(m.content), language="json", wrap_lines=True)


model, missing = get_model()
if model is None:
    st.error("Thiếu cấu hình trong .env: " + ", ".join(missing))
    st.stop()
if "agent" not in st.session_state:
    open_session()

with st.sidebar:
    st.header(st.session_state.session_id)
    if st.button("Mở session mới (history rỗng)", use_container_width=True, type="primary"):
        open_session()
        st.rerun()

    st.subheader("Memory đã nạp vào session này")
    st.code(st.session_state.memory_text or "(rỗng)", language=None, wrap_lines=True)
    st.caption("Chỉ nạp một lần lúc mở session. Quy ước agent vừa ghi sẽ có hiệu lực từ session sau.")

    st.subheader("MEMORY.md trên đĩa (hiện tại)")
    memory_file = memory_store.MEMORY_FILE
    st.code(memory_file.read_text(encoding="utf-8") if memory_file.exists() else "(chưa có file)", language=None, wrap_lines=True)

    st.subheader("workspace/output/")
    st.write(sorted(p.name for p in OUTPUT_DIR.glob("*.md")) if OUTPUT_DIR.exists() else "(trống)")

    with st.expander("Làm lại từ đầu (xóa memory và output)"):
        confirmed = st.checkbox("Mình chắc chắn muốn xóa")
        if st.button("Xóa", disabled=not confirmed):
            memory_store.reset()
            shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
            open_session()
            st.rerun()

st.title("Bài 5 · Chat với agent có persistent memory")

if not st.session_state.history:
    st.info(
        "**Cách thử:**\n"
        "1. Nói: *Quy ước: báo cáo ghi vào output/bao-cao-YYYY-MM-DD.md, tiếng Việt, dòng đầu TL;DR:. Hãy ghi nhớ.* "
        "→ thấy tool `remember_convention`, thanh bên hiện dòng `[active]`.\n"
        "2. Bấm **Mở session mới** → history rỗng, thanh bên hiện memory đã nạp.\n"
        "3. Nói: *Hôm nay là 2026-10-21. Đọc data/weekly_notes.md rồi viết báo cáo tuần.* (không nhắc quy ước) "
        "→ file được đặt đúng tên.\n"
        "4. Đổi quy ước (tên `report-YYYY-MM-DD.md`, tiếng Anh), mở session mới, lặp lại bước 3."
    )

for message in st.session_state.history:
    render_message(message)

if prompt := st.chat_input("Nhắn cho agent..."):
    with st.spinner("Agent đang chạy vòng lặp..."):
        try:
            result = st.session_state.agent.invoke(
                {"messages": st.session_state.history + [HumanMessage(prompt)]},
                config={"recursion_limit": RECURSION_LIMIT},
            )
            st.session_state.history = result["messages"]
        except Exception as error:  # hiện lỗi thay vì làm sập giao diện
            st.error(f"Lỗi khi chạy agent: {error}")
            st.stop()
    st.rerun()
