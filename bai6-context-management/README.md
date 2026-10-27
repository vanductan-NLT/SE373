# BTVN#6 · Challenge B: Context management

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11 · **Nhóm:** 15

Giữ context nhỏ gọn mà agent vẫn làm đúng việc (Slide Buổi 7, tr. 18-34).

| | Nội dung | Chạy |
|---|---|---|
| **B1 Compact** (bắt buộc) | Session debug dài; `CompactionMiddleware` rút gọn tool output, tạo structured checkpoint 7 trường, thay messages; agent vẫn nhớ lỗi, cách đã thử, ràng buộc, bước tiếp | `python run_demo_b1.py` |
| **B2 Code Mode** (điểm cộng) | Cùng một câu hỏi trên 50 file log: native (`read_file`) so với Code Mode (`run_python`), đo `usage` | `python run_demo_b2.py` |

Báo cáo nộp: [BAO_CAO.pdf](BAO_CAO.pdf) (dựng từ output thật bằng `python scripts/build_report_pdf.py`). Thiết kế chi tiết: [THIET_KE.md](THIET_KE.md). Output demo thật: `demo-b1.txt`, `demo-b2.txt`; token từng lần gọi model: `traces/*.jsonl`.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # rồi điền DEEPSEEK_API_KEY (không commit .env)
```

## Chạy

```bash
python test_offline.py          # kiểm tra không cần API: điểm cắt không mồ côi ToolMessage, prune, middleware (model giả), bộ chấm, run_python
python run_demo_b1.py           # B1: compact rồi đối chứng không compact (thêm --no-baseline để bỏ đối chứng)
python run_demo_b2.py           # B2: 50 file rồi 10 file, native và Code Mode (--files N, --mode native|code)
python fixtures/make_logs.py    # sinh lại 50 file log + đáp án (run_demo_b2.py tự gọi nếu thiếu)
python scripts/build_report_pdf.py  # dựng BAO_CAO.pdf từ demo-b1.txt, demo-b2.txt, traces/ (cần Edge hoặc Chrome)
python scripts/package_source.py    # đóng gói zip nộp bài (Nhom15_ChallengeB.zip) vào output/
```

## Cấu trúc

```
config.py, paths.py       cấu hình, ngưỡng compact (COMPACT_TRIGGER_TOKENS), giới hạn vòng lặp, đường dẫn
agent.py, prompts.py      dựng agent (create_agent + DeepSeek), system prompt
token_log.py              callback ghi input/output tokens, cache hit mỗi lần gọi model → JSONL
compaction.py             B1: CompactionMiddleware + Checkpoint (slide 21-26)
pruning.py                B1: rút gọn tool output (giữ dòng lỗi, gộp dòng lặp, archive raw) (slide 19, 23)
tools/debug_tools.py      B1: read_log, run_tests, apply_fix (giả, dữ liệu sinh deterministic)
tools/code_mode.py        B2: run_python(code) (slide 28-31)
tools/files.py            B2 native: read_file, list_files (từ bài 5)
fixtures/make_logs.py     B2: sinh 50 file log + ground truth
run_demo_b1.py            B1 demo + tự kiểm PASS/FAIL
run_demo_b2.py            B2 so sánh native vs Code Mode
test_offline.py           kiểm tra không cần API
scripts/                  build_report_pdf.py (dựng báo cáo PDF), show_prune_example.py, package_source.py
```

Lưu ý: `run_python` chạy trong tiến trình con có timeout, cwd = `workspace/`, env tối thiểu (không có API key) nhưng **không phải sandbox bảo mật**. Chỉ dùng với dữ liệu giả.
