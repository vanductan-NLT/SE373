# BTVN#2 - Issue Triage mini-app

**Sinh viên:** Văn Đức Tân - **MSSV:** 24521586 - **Lớp:** SE373.R11

Ứng dụng nhận mô tả issue phần mềm, yêu cầu DeepSeek trả dữ liệu có cấu trúc,
kiểm tra bằng Pydantic và minh họa function calling do application kiểm soát.

## Cài đặt và chạy

```powershell
cd bai2-issue-triage
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Điền DEEPSEEK_API_KEY trong .env
python cli.py
python cli.py --write-cost-report
python -m streamlit run streamlit_app.py
python -m pytest
```

CLI và Streamlit dùng chung workflow:

1. Instruction nằm trong system prompt, input nằm riêng trong `<issue_text>`.
2. Model trả JSON; application parse và validate thành `IssueTriage`.
3. Với component thuộc allowlist, model đề xuất `get_component_owner`.
4. Application kiểm tra tool/arguments, thực thi lookup, gửi tool result về model.
5. Giao diện in trace `tool_call -> application executes -> tool_result -> final response`.

Không có agent loop, RAG, memory, retry/backoff hoặc multi-tool orchestration.

## Bài nộp

Sau khi chạy live và chụp ảnh theo [docs/BAO_CAO.md](docs/BAO_CAO.md):

```powershell
python scripts/package_source.py
python scripts/build_report.py --drive-url "LINK_GOOGLE_DRIVE_PUBLIC"
```

ZIP tự động loại `.env`, Git metadata, cache và virtual environment.
