# BTVN#5 · Challenge A: Persistent memory (Buổi 7)

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11

Agent nhớ quy ước dự án qua nhiều session và cập nhật khi quy ước đổi. Agent nền là `stage-01-files` của BTVN#4
(LangChain `create_agent`, tool `read_file`/`write_file`/`list_files`), thêm 1 tool `remember_convention` và một file memory.

Slide present: [slide.html](slide.html) (mở bằng trình duyệt, F11 để toàn màn hình).

## Thiết kế (trả lời 5 gợi ý của đề)

| Câu hỏi | Lựa chọn |
|---|---|
| Lưu ở đâu | `memory/MEMORY.md`, mỗi dòng một quy ước (`topic` + `rule`). Ngoài `workspace/` nên `write_file` không ghi đè được |
| Ai ghi | Agent gọi tool `remember_convention(topic, rule)`; code (`memory_store.py`) lo thay thế dòng cũ |
| Khi nào nạp | Lúc mở session, nạp các dòng `active` vào cuối system prompt |
| Khi quy ước đổi | Cùng `topic`: dòng cũ thành `[superseded <time> bởi session-N]`, thêm dòng `active` mới |
| Kiểm chứng | In khối `MEMORY INJECTED` mỗi session; code kiểm file báo cáo thật sự được tạo |

## Chạy

Dùng lại key DeepSeek của bài 3: copy `.env.example` thành `.env` rồi điền (hoặc copy `.env` từ bài 3).

```powershell
cd bai5-persistent-memory
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run_demo.py --reset
```

`run_demo.py` chạy 4 session, mỗi session dựng agent mới với history rỗng:

1. Session 1: chốt quy ước (tên `bao-cao-YYYY-MM-DD.md`, tiếng Việt, dòng đầu `TL;DR:`).
2. Session 2: "viết báo cáo tuần", không nhắc lại quy ước. Chứng minh 1.
3. Session 3: đổi quy ước (tên `report-YYYY-MM-DD.md`, tiếng Anh).
4. Session 4: cùng câu lệnh như session 2. Chứng minh 2.

Kết quả ghi ở `demo-log.txt`, memory cuối cùng ở `memory/MEMORY.md`. Code tự kiểm: session 2 chỉ tạo `bao-cao-2026-10-21.md`
(dòng đầu `TL;DR:`, tiếng Việt), session 4 chỉ tạo `report-2026-10-21.md` (tiếng Anh).

## File

| File | Vai trò |
|---|---|
| `memory_store.py` | Đọc/ghi `MEMORY.md`, thay thế dòng cũ theo `topic`, render khối nạp vào prompt |
| `tools/memory.py` | Tool `remember_convention` |
| `agent.py`, `prompts.py` | Agent stage-01 + nạp memory vào system prompt mỗi session |
| `config.py`, `paths.py`, `tools/files.py` | Copy nguyên từ `stage-01-files` |
| `run_demo.py` | 4 session + tự kiểm PASS/FAIL |

## Ghi chú

- Lần chạy đầu và lần chạy sau khi sửa đều PASS. Một lần chạy giữa chừng, agent tự ghi thêm câu "quy ước cũ là bao-cao-…" vào rule mới, làm memory lẫn thông tin lỗi thời. Đã sửa bằng một dòng prompt: rule chỉ chứa quy ước hiện hành, lịch sử do code giữ.
- Model sinh ngẫu nhiên nên mỗi lần chạy lời văn khác nhau; tên file và dòng đầu `TL;DR:` ổn định.
- `workspace/output/` và `.env` không được commit.
