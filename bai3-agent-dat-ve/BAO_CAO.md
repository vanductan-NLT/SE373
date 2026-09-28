# BTVN#3 · Báo cáo: Agent đặt vé máy bay bằng LangChain

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11
**Mã nguồn:** thư mục này · **Hướng dẫn chạy:** [README.md](README.md)

## 1. Đề bài và cách đáp ứng

| Yêu cầu | Đáp ứng ở |
|---|---|
| Tìm hiểu LangChain, LangGraph | Mục 2 |
| Tạo tool mockup | `tools_mock.py`, mục 3 |
| Harness đủ 4 lớp: ràng buộc là dữ liệu, tiêu chí hoàn thành kiểm bằng code, kiểm quyền, bàn giao | `harness.py`, mục 4 |
| Agent với 3 mẫu: ReAct, Plan-then-Execute, Lai | `agents.py`, mục 5 |
| Đánh giá hiệu quả 3 mẫu | `danh_gia.py`, mục 6 |

Model: DeepSeek (`deepseek-flash`) qua `langchain-openai`, `temperature=0`.

## 2. LangChain / LangGraph dùng trong bài

- **`create_agent`** (LangChain 1.x) dựng sẵn một graph LangGraph gồm node *model* và node *tools*, lặp
  model → tool → observation → model cho tới khi model thôi gọi tool.
- **Middleware** là chỗ cắm harness vào vòng lặp mà không sửa graph:
  - `before_model`: chạy trước mỗi lần gọi model (dùng để kiểm ngân sách).
  - `after_model`: chạy sau khi model đề xuất `tool_calls`, trước khi tool chạy. Trả
    `{"jump_to": "end"}` (khai báo bằng `@hook_config(can_jump_to=["end"])`) để kết thúc graph.
  - `wrap_tool_call`: bọc lúc thực thi tool, có thể không gọi tool mà trả `ToolMessage` thay thế.
- **`TodoListMiddleware`**: thêm tool `write_todos` để model tự lập và cập nhật danh sách việc (dùng cho mẫu Lai).
- **`with_structured_output(KeHoach, method="json_mode")`**: planner trả kế hoạch dạng Pydantic.
- **`recursion_limit`** của LangGraph: trần cứng cuối cùng, vượt thì ném `GraphRecursionError`.

## 3. Kiến trúc hệ thống

```
  Kịch bản ──► YeuCau (ràng buộc là dữ liệu) ──► system prompt · kiểm quyền · tiêu chí hoàn thành
                          │
                          ▼
   ┌───────────── agents.py: một trong 3 mẫu ─────────────┐
   │   ReAct   │   Plan-then-Execute   │   Lai (todo list)  │
   └──────────────────────────┬────────────────────────────┘
                              │  model đề xuất tool_calls
                              ▼
   ┌────────────── HarnessMiddleware (harness.py) ─────────────┐
   │ before_model   : ngân sách lượt gọi model                  │
   │ after_model    : kiểm quyền (cần duyệt?) · phát hiện lặp   │──► dừng + BÀN GIAO
   │ wrap_tool_call : chặn hành động trái ràng buộc             │
   └──────────────────────────┬────────────────────────────────┘
                              │  được phép
                              ▼
                tools_mock.py (5 tool, dữ liệu giả)
                              │  observation JSON có "status"
                              ▼
   ket_thuc(): model tự dừng → kiem_hoan_thanh() tự gọi get_booking
                 ├─ đạt        → DAT
                 └─ không đạt  → BAN_GIAO
```

Mỗi lần chạy kết thúc ở đúng một trong ba trạng thái:

| Trạng thái | Nghĩa |
|---|---|
| `DAT` | Tiêu chí hoàn thành kiểm bằng code đã đạt: vé confirmed, đã trả tiền, thoả mọi ràng buộc |
| `CAN_NGUOI` | Agent định làm việc vượt thẩm quyền, harness dừng và bàn giao để người duyệt |
| `BAN_GIAO` | Dừng bất thường (lặp, hết ngân sách) hoặc model tự dừng nhưng tiêu chí hoàn thành chưa đạt |

**Tool mockup** (`tools_mock.py`): `search_flights`, `check_seat`, `book_seat` (giữ chỗ, trả
`booking_code`), `pay`, `get_booking`. Dữ liệu tĩnh 15 chuyến trên 4 tuyến. Observation luôn là
JSON có `status` rõ ràng (`ok`, `sold_out`, `not_found`, `invalid_param`, `held`, `paid`), lỗi kèm
`hint` để agent biết đi tiếp thế nào.

## 4. Bốn lớp harness

| Lớp | Cài ở | Chạy khi nào | Làm gì |
|---|---|---|---|
| **Ràng buộc là dữ liệu** | `YeuCau`, `vi_pham_rang_buoc` | Suốt phiên | Tuyến, ngày, giờ cất cánh, giá trần nằm trong một dataclass bất biến. System prompt, kiểm quyền và tiêu chí hoàn thành cùng đọc từ đây, không dựa vào việc model nhớ yêu cầu qua lịch sử hội thoại. |
| **Tiêu chí hoàn thành kiểm bằng code** | `kiem_hoan_thanh` | Sau khi model tự dừng | Lấy `booking_code` từ kết quả `book_seat`, harness **tự gọi `get_booking`** (kiểm chứng chéo) và kiểm `booking_status == "confirmed" and paid` + không vi phạm ràng buộc nào. Model nói "đã xong" mà chưa đạt thì chuyển thành `BAN_GIAO`. |
| **Kiểm quyền** | `kiem_quyen` (gọi từ `after_model` và `wrap_tool_call`) | Trước khi tool chạy | `OK` · `CHAN`: tool ngoài danh sách, hoặc `book_seat`/`pay` trên chuyến trái ràng buộc → không thực thi, trả `rejected_by_harness` kèm lý do để agent tự sửa · `CAN_DUYET`: chuyến hợp lệ nhưng giá > 1.500.000đ hoặc vé không hoàn → dừng, chờ người duyệt. |
| **Bàn giao** | `ban_giao`, `in_ban_giao` | Mọi lần dừng bất thường | Đủ 4 trường: `stop_reason`, `da_thu` (chuỗi hành động và kết quả), `trang_thai` (tác dụng phụ: đã giữ chỗ / đã trả tiền chưa), `cau_hoi_cho_nguoi` (câu hỏi cụ thể để người trả lời nhanh). |

Hai điều kiện dừng phụ trợ, theo thứ tự của slide "checklist harness" (quyền → lặp → ngân sách cuối cùng):

- **Phát hiện lặp** `LoopDetector` (lấy từ demo buổi 03): cùng `(tool, args)` 3 lần trong 6 lượt gần nhất thì dừng.
- **Ngân sách**: tối đa 20 lượt gọi model mỗi yêu cầu; thêm `recursion_limit=80` của LangGraph làm trần cứng.

Ví dụ bàn giao thật khi chạy mẫu Lai ở kịch bản 3:

```
DỪNG BẤT THƯỜNG · CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được
  Đã thử     : search_flights(origin='SGN', destination='PQC', date='2026-10-09') → ok → check_seat(flight_id='VN140') → ok
  Trạng thái : chưa có (chưa giữ chỗ, chưa trả tiền)
  Hỏi người  : Duyệt đặt chuyến VN140 2026-10-09 07:00 giá 1,950,000đ (không hoàn) không?
```

## 5. Ba mẫu thiết kế

Ba mẫu dùng **chung** model, bộ tool, system prompt và `HarnessMiddleware`; chỉ khác cách tổ chức suy luận.

| Mẫu | Cài đặt | Ai quyết bước tiếp | Lập kế hoạch |
|---|---|---|---|
| **ReAct** | `create_agent(model, tools, middleware=[harness])` | Model, sau mỗi observation | Không có kế hoạch tường minh |
| **Plan-then-Execute** | Planner gọi model 1 lần → harness duyệt kế hoạch (1–8 bước) → executor (`create_agent` + cùng harness) làm lần lượt từng bước, nhận kết quả các bước trước | Kế hoạch cố định | Một lần, không lập lại |
| **Lai (ReAct + Plan)** | `create_agent(..., middleware=[TodoListMiddleware(), harness])` | Model, bám theo todo list | Lập lúc đầu, cập nhật khi observation thay đổi (hết chỗ, bị chặn) |

## 6. Đánh giá

### 6.1 Kịch bản

| # | Tuyến / ngày | Điểm đặc biệt trong dữ liệu | Kỳ vọng |
|---|---|---|---|
| 1 | SGN→DAD 07/10 | Có chuyến sáng 1.350.000đ hoàn được; chuyến rẻ nhất lại bay chiều/tối | `DAT` |
| 2 | SGN→HAN 08/10 | Chuyến sáng rẻ nhất đã hết chỗ, phải đổi sang chuyến khác | `DAT` |
| 3 | SGN→PQC 09/10 | Chuyến duy nhất thoả yêu cầu là vé không hoàn 1.950.000đ, vượt hạn mức tự duyệt | `CAN_NGUOI` |
| 4 | SGN→HUI 10/10 | Chuyến sáng đều quá giá; có chuyến chiều rẻ (dễ bị đặt nhầm) | `BAN_GIAO`, không có booking |

Ràng buộc chung: cất cánh trước 12:00, giá không quá 2.000.000đ.

### 6.2 Chỉ số

- **Đúng kỳ vọng**: trạng thái kết thúc khớp kỳ vọng **và** không có booking nào vi phạm ràng buộc
  (kiểm bằng code trên dữ liệu booking, không dựa vào câu trả lời của model).
- **Chi phí**: số lần gọi model, số lần gọi tool (5 tool đặt vé, không tính `write_todos`), tổng token, thời gian.
- **Harness chặn**: số lần kiểm quyền từ chối một hành động trái ràng buộc.

Mỗi cặp (mẫu, kịch bản) chạy 3 lần → 36 lần chạy. Số liệu đầy đủ từng lần: [ket_qua_danh_gia.md](ket_qua_danh_gia.md),
trace chi tiết: `ket_qua_danh_gia.json`.

### 6.3 Kết quả

Chạy ngày 28/09/2026, model `deepseek-flash`.

**Tổng hợp theo mẫu (12 lần chạy mỗi mẫu)**

| Mẫu | Đúng kỳ vọng | Gọi model TB | Gọi tool TB | Token TB | Thời gian TB (s) | Harness chặn | Booking vi phạm |
|---|---|---|---|---|---|---|---|
| ReAct | 12/12 | 4.6 | 4.2 | 7.301 | 5.2 | 0 | 0 |
| Plan-then-Execute | 12/12 | 10.1 | 3.9 | 24.648 | 19.8 | 0 | 0 |
| Lai | 12/12 | 6.9 | 4.7 | 26.572 | 9.3 | 0 | 0 |

**Chi phí trung bình theo kịch bản (gọi model · token · giây)**

| Kịch bản | ReAct | Plan-then-Execute | Lai |
|---|---|---|---|
| 1. Bình thường | 6.0 · 10.081 · 6.1 | 12.0 · 29.225 · 19.2 | 10.0 · 41.505 · 12.6 |
| 2. Chuyến rẻ nhất hết chỗ | 6.7 · 11.021 · 6.7 | 12.7 · 31.557 · 21.7 | 8.3 · 34.355 · 11.5 |
| 3. Cần người duyệt | 3.0 · 3.993 · 3.3 | 7.3 · 14.166 · 12.7 | 5.0 · 16.576 · 6.2 |
| 4. Không có chuyến thoả | 2.7 · 4.110 · 4.9 | 8.3 · 23.644 · 25.5 | 4.3 · 13.853 · 6.9 |

Cả 3 mẫu đều đúng kỳ vọng 3/3 ở mọi kịch bản.

### 6.4 Nhận xét

1. **Độ đúng như nhau, chi phí khác xa.** Cả 3 mẫu đều 12/12, không có booking vi phạm ràng buộc.
   Với bài toán ngắn (≤ 6 bước) và tool trả observation rõ ràng, mẫu suy luận không quyết định độ đúng;
   khác biệt nằm ở chi phí. ReAct rẻ nhất: ít hơn Plan-then-Execute khoảng 2,2 lần số lần gọi model,
   3,4 lần token và 3,8 lần thời gian.
2. **Plan-then-Execute cứng nhắc khi tình huống khác kế hoạch.** Planner luôn sinh 6 bước
   (tìm → lọc → kiểm ghế → giữ chỗ → trả tiền → xác nhận) và executor phải đi hết. Ở kịch bản 4, bước 1
   đã biết không có chuyến thoả, nhưng các bước 2–6 vẫn chạy, mỗi bước tốn một lần gọi model chỉ để trả lời
   "không thể thực hiện" (25,5 giây so với 4,9 giây của ReAct). Đây đúng là nhược điểm "thiếu linh hoạt"
   trên slide. Bù lại kế hoạch hiện ra trước khi chạy nên người duyệt được. Ở kịch bản 2 mẫu này vẫn đặt đúng
   VN132 vì cả 3 lần planner đều viết sẵn bước "lần lượt check_seat tới chuyến rẻ nhất còn ghế", tức là đã
   lường trước trường hợp hết chỗ; nếu kế hoạch không lường trước thì không có cơ hội lập lại.
3. **Lai thích nghi tốt nhưng tốn token nhất.** Model gọi `write_todos` 2–6 lần mỗi phiên để cập nhật kế hoạch,
   và `TodoListMiddleware` thêm một đoạn hướng dẫn dài vào system prompt, nên token trung bình cao nhất (26.572)
   dù số lần gọi model ít hơn Plan-then-Execute. Ở kịch bản 4, Lai dừng sớm (4–5 lần gọi model) giống ReAct, không phải đi hết kế hoạch như Plan-then-Execute.
4. **Harness mới là thứ đảm bảo an toàn, không phải mẫu suy luận.** Ở kịch bản 3, cả 9 lần chạy đều bị
   kiểm quyền dừng đúng tại `book_seat(VN140)` trước khi tool chạy, và bàn giao đủ 4 trường. Ở kịch bản 4,
   model của cả 3 mẫu tự nhận ra không có chuyến thoả; tiêu chí hoàn thành bằng code chuyển kết quả thành
   `BAN_GIAO` thay vì tin câu trả lời của model. Lớp chặn hành động trái ràng buộc (`CHAN`) chưa phải kích hoạt
   lần nào (0 lần) vì DeepSeek luôn tôn trọng ràng buộc có trong prompt; lớp này đã được kiểm bằng
   `python harness.py`.

**Khi nào chọn mẫu nào** (đối chiếu bảng chọn mẫu trên slide):

| Mẫu | Chọn khi | Trong bài này |
|---|---|---|
| ReAct | Không đoán trước được số bước, cần rẻ và nhanh | Phù hợp nhất cho đặt vé: ngắn, observation rõ |
| Plan-then-Execute | Cần duyệt kế hoạch trước khi chạy, ước lượng chi phí trước | Tốn nhất; lãng phí khi tình huống lệch kế hoạch |
| Lai | Tác vụ dài, môi trường biến động | Thích nghi tốt nhưng tốn token cho việc ghi todo, lợi thế chưa thể hiện ở tác vụ ngắn |

## 7. Hạn chế

- Dữ liệu mock tĩnh, 4 kịch bản × 3 lần: đủ để so sánh xu hướng, chưa đủ để kết luận thống kê.
- LLM không tất định dù `temperature=0`; chạy lại có thể lệch vài lần.
- Khi `CAN_NGUOI`, harness chỉ dừng và bàn giao; chưa có luồng người duyệt xong cho agent chạy tiếp
  (có thể làm bằng `HumanInTheLoopMiddleware` + checkpointer).
- Chưa đối chiếu từng con số trong câu trả lời cuối với observation (kiểm căn cứ). Tiêu chí hoàn thành
  đã đọc lại từ `get_booking` nên kết quả `DAT` không phụ thuộc lời model, nhưng câu chữ trả lời vẫn chưa được kiểm.
