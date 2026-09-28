# BTVN#3 · Agent đặt vé máy bay bằng LangChain

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11

Agent đặt vé trên bộ tool mockup, có lớp harness (ràng buộc là dữ liệu, tiêu chí hoàn thành
kiểm bằng code, kiểm quyền, bàn giao) và cài theo 3 mẫu: ReAct, Plan-then-Execute, Lai.
Báo cáo: [BAO_CAO.md](BAO_CAO.md) · Kết quả đánh giá: [ket_qua_danh_gia.md](ket_qua_danh_gia.md)

## Cài đặt

```powershell
cd bai3-agent-dat-ve
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Điền DEEPSEEK_API_KEY trong .env (giống bài 2)
```

## Chạy

```powershell
python harness.py                          # tự kiểm harness, không gọi API
python main.py --mau react --kich-ban 1    # mau: react | plan | lai ; kich-ban: 1..4
python danh_gia.py                         # 4 kịch bản × 3 mẫu × 3 lần → ket_qua_danh_gia.md
```

| File | Vai trò |
|---|---|
| `tools_mock.py` | Dữ liệu chuyến bay giả + 5 tool: `search_flights`, `check_seat`, `book_seat`, `pay`, `get_booking` |
| `harness.py` | 4 lớp harness + phát hiện lặp + ngân sách, cắm vào agent qua `HarnessMiddleware` |
| `agents.py` | 3 mẫu agent dùng chung model, tool, harness |
| `main.py` | Chạy 1 mẫu trên 1 kịch bản, in trace |
| `danh_gia.py` | Chạy đánh giá, ghi bảng kết quả |
