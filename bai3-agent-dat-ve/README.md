# BTVN#3 · Agent đặt vé máy bay bằng LangChain

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11

Agent đặt vé trên bộ tool mockup, có lớp harness (ràng buộc là dữ liệu, tiêu chí hoàn thành
kiểm bằng code, kiểm quyền, bàn giao) và cài theo 3 mẫu: ReAct, Plan-then-Execute, Lai.
Báo cáo: [BAO_CAO.md](BAO_CAO.md)

| File | Vai trò |
|---|---|
| `tools_mock.py` | Dữ liệu chuyến bay giả + 5 tool: `search_flights`, `check_seat`, `book_seat`, `pay`, `get_booking` |
| `harness.py` | 4 lớp harness + phát hiện lặp + ngân sách, cắm vào agent qua `HarnessMiddleware` |
| `agents.py` | 3 mẫu agent dùng chung model, tool, harness |
| `main.py` | Chạy 1 mẫu trên 1 kịch bản, in trace |
| `danh_gia.py` | Chạy đánh giá, ghi `ket_qua_danh_gia.md` và `ket_qua_danh_gia.json` |

## Hướng dẫn chạy

Cần Python 3.10 trở lên và API key DeepSeek (dùng lại key của bài 2).

### Bước 1 · Tải code và cài thư viện

```powershell
git clone https://github.com/vanductan-NLT/SE373.R11.git
cd SE373.R11\bai3-agent-dat-ve
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Nếu PR chưa merge vào `main`, chạy thêm `git checkout feat/tach-bai-va-bai3` sau lệnh `git clone`.

### Bước 2 · Điền API key

```powershell
Copy-Item .env.example .env
notepad .env
```

Sửa dòng `DEEPSEEK_API_KEY=` thành key thật. `DEEPSEEK_MODEL` để giống bài 2.
File `.env` đã nằm trong `.gitignore`, không bị commit.

### Bước 3 · Kiểm tra harness (không tốn tiền, không cần key)

```powershell
python harness.py
```

Kết quả đúng: `VJ122 → OK`, `VN126 → CHAN` (bay chiều), `VN120 → CAN_DUYET` (vượt hạn mức),
tiêu chí hoàn thành `dat: False` trước khi pay và `dat: True` sau khi pay, LoopDetector báo ở V3.

### Bước 4 · Chạy thử từng mẫu

```powershell
python main.py --mau react --kich-ban 1
python main.py --mau plan --kich-ban 2
python main.py --mau lai --kich-ban 3
```

`--mau` là `react`, `plan` hoặc `lai`; `--kich-ban` từ 1 đến 4. Chương trình in trace từng vòng,
kết quả (`DAT` / `CAN_NGUOI` / `BAN_GIAO`), chi phí và bản bàn giao nếu dừng bất thường.

### Bước 5 · Chạy đánh giá (4 kịch bản × 3 mẫu × 3 lần = 36 lần chạy, khoảng 15–30 phút)

```powershell
python danh_gia.py
```

Chạy nhanh để thử: `python danh_gia.py --lap 1`. Chỉ một mẫu: `python danh_gia.py --mau react`.
Xong sẽ có `ket_qua_danh_gia.md` (bảng) và `ket_qua_danh_gia.json` (kèm trace từng lần).

`BAO_CAO.md` đã có số liệu của một lần chạy đầy đủ. Chạy lại sẽ ghi đè `ket_qua_danh_gia.md`;
số liệu có thể lệch vài lần vì LLM không tất định.

### Lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `Thiếu DEEPSEEK_API_KEY` | Chưa tạo `.env` hoặc còn để `your_deepseek_api_key_here` |
| `model not found` / 400 từ API | Sửa `DEEPSEEK_MODEL` trong `.env` cho giống bài 2 |
| `Activate.ps1 cannot be loaded` | Chạy `Set-ExecutionPolicy -Scope Process Bypass` rồi activate lại |
