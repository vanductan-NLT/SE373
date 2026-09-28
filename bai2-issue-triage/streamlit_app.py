"""Streamlit UI for Issue Triage."""

import os
import streamlit as st

from cli import DEFAULT_ISSUE
from issue_triage.config import ConfigurationError, Settings
from issue_triage.workflow import TriageWorkflow, validate_issue_text

st.set_page_config(page_title="Issue Triage", page_icon="🧭", layout="wide")


def render_result(result) -> None:
    cols = st.columns(4)
    for col, label, value in zip(cols, ["Status", "Severity", "Component", "Owner"], [result.triage.status, result.triage.severity or "-", result.triage.component or "-", result.owner or "Không tra cứu"]):
        col.metric(label, value)
    st.subheader("IssueTriage đã validate")
    st.json(result.triage.model_dump(mode="json"))
    with st.expander("Trace: tool_call → application executes → tool_result → final", expanded=True):
        if not result.tool_traces:
            st.info("Không chạy tool vì status/component không phù hợp.")
        for trace in result.tool_traces:
            st.markdown("**1. tool_call**"); st.json({"id": trace.call_id, "name": trace.name, "arguments": trace.arguments})
            st.markdown("**2. application executes**"); st.code(f"get_component_owner({trace.arguments['component']!r})", language="python")
            st.markdown("**3. tool_result**"); st.json(trace.result)
        st.markdown("**4. final response**"); st.write(result.final_response)
    st.subheader("Kết quả cuối"); st.success(result.final_response)
    st.caption(f"Token usage: input={result.total_input_tokens:,} · output={result.total_output_tokens:,}")


def main() -> None:
    with st.sidebar:
        st.header("Runtime"); st.write("DeepSeek OpenAI-compatible API")
        st.code(os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com", language=None)
        st.code(os.getenv("DEEPSEEK_MODEL") or "deepseek-flash", language=None)
        st.write("Tool allowlist: payment, identity, search")
    st.title("Issue Triage")
    st.write("Structured output bằng Pydantic và function calling do application kiểm soát.")
    with st.form("triage-form"):
        issue = st.text_area("Mô tả issue", value=DEFAULT_ISSUE, height=180)
        submitted = st.form_submit_button("Phân loại issue", use_container_width=True)
    if not submitted:
        return
    try:
        issue = validate_issue_text(issue)
        settings = Settings.from_environment()
        with st.spinner("Đang gọi DeepSeek và kiểm tra output..."):
            result = TriageWorkflow(settings.create_client(), settings.model).run(issue)
    except (ConfigurationError, ValueError, RuntimeError) as error:
        st.error(f"Triage không hoàn tất: {error}"); st.info("Kiểm tra .env; không chia sẻ API key."); return
    except Exception as error:
        st.error(f"DeepSeek API không hoàn tất yêu cầu: {type(error).__name__}")
        st.info("Kiểm tra kết nối, số dư API và model trong .env; không chia sẻ API key.")
        return
    render_result(result)


if __name__ == "__main__":
    main()
