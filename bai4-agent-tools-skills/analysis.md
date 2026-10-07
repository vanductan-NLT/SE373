# Báo cáo Phân tích & Thực nghiệm Toàn diện: Lab Agent Tools & Skills

**Môn học:** Agentic AI Engineering  
**Học viên:** Văn Đức Tân - MSSV: 24521586  
**Nội dung bài tập:** Hoàn thiện cả 2 Block bài tập (Block 1: Tra cứu chính sách hoàn tiền & Block 2: Phân tích khối lượng công việc và kiểm tra quá tải)  
**Mô hình LLM sử dụng:** DeepSeek API (`deepseek-chat`, format OpenAI-compatible)

---

# PHẦN 1: BÀI TẬP BLOCK 1 (STAGES 00 - 02)
## Tra cứu chính sách đúng phiên bản bằng Tool Use & Skill Use

### 1.1. Kết quả kiểm tra trực tiếp tool `list_files`

Tool `list_files(path: str)` được thiết kế và triển khai trong `tools/files.py` (đồng bộ tại `stage-01-files` và `stage-02-skills`) với các nguyên tắc kiến trúc:
- **Không duyệt đệ quy**: Chỉ trả về danh sách các mục con trực tiếp trong thư mục mục tiêu.
- **Dữ liệu có cấu trúc**: Trả về mảng JSON chứa các đối tượng có thuộc tính `name`, `path` (đường dẫn tương đối so với workspace), `type` (`file` hoặc `directory`).
- **Tính tất định (Deterministic)**: Sắp xếp tăng dần theo `name`.
- **An toàn sandbox**: Chặn đứng path traversal (`..`), đường dẫn tuyệt đối ra ngoài workspace, symlink trỏ ra ngoài hệ thống file cho phép.
- **Xử lý lỗi chuẩn mực**: Trả về JSON chứa mã lỗi cụ thể: `DIRECTORY_NOT_FOUND` (thư mục không tồn tại), `NOT_A_DIRECTORY` (đường dẫn là file), `PATH_OUTSIDE_WORKSPACE` (thoát workspace).

#### Bảng kết quả kiểm thử trực tiếp tool `list_files`:

| STT | Kịch bản kiểm thử | Input `path` | Output thực tế | Kết quả | Ý nghĩa / Ghi chú |
|---|---|---|---|:---:|---|
| 1 | Thư mục hợp lệ | `data` | `{"ok": true, "path": "data", "items": [{"name": "alpha.txt", "path": "data/alpha.txt", "type": "file"}, ...]}` | **PASS** | Liệt kê đầy đủ file/folder con, định dạng chuẩn. |
| 2 | Đường dẫn là file | `data/note.md` | `{"ok": false, "error": {"code": "NOT_A_DIRECTORY", "message": "Đây là file, không phải thư mục: data/note.md"}}` | **PASS** | Phân biệt file và folder, không trả danh sách rỗng. |
| 3 | Thư mục không tồn tại | `data/nonexistent` | `{"ok": false, "error": {"code": "DIRECTORY_NOT_FOUND", "message": "Không tìm thấy thư mục: data/nonexistent"}}` | **PASS** | Báo lỗi rõ ràng để agent xử lý bước kế tiếp. |
| 4 | Path traversal | `../` | `{"ok": false, "error": {"code": "PATH_OUTSIDE_WORKSPACE", "message": "Đường dẫn thoát ra ngoài workspace: ../"}}` | **PASS** | Đảm bảo an toàn sandbox workspace. |

> **Unit tests:** 19 test cases trong `test_files.py` và 5 test cases trong `test_skill_catalog.py` vượt qua toàn bộ.

---

### 1.2. Bảng kết quả thực nghiệm các kịch bản Block 1 (Có đối chiếu Trace)

Tất cả các lượt tương tác đều được ghi nhận bằng trace file JSONL thực tế được sinh ra khi gọi model `deepseek-chat`:

| Kịch bản | Câu hỏi của người dùng | Hành vi của Agent & Công cụ sử dụng | Kết luận & Trích dẫn trả lời | Trace File |
|---|---|---|---|---|
| **Trường hợp A: Mua trước 01/10/2026** | *"Tôi mua ngày 28/09/2026, yêu cầu hoàn ngày 06/10/2026, chưa kích hoạt. Tôi có được hoàn không?"* | 1. Đọc `SKILL.md` của `refund-policy`.<br>2. Gọi `list_files("data/policies")`.<br>3. Gọi `read_file("data/policies/policy-before-oct.md")`.<br>4. Tính số ngày: $06/10 - 28/09 = 8$ ngày.<br>5. Đọc `answer-template.md`. | **Không đủ điều kiện**.<br>- Chính sách: Trước tháng 10.<br>- Số ngày: 8 ngày.<br>- Lý do: Quá hạn 7 ngày quy định (8 > 7).<br>- Phí hoàn tiền: Không áp dụng.<br>- Căn cứ: `data/policies/policy-before-oct.md`. | `stage-02-skills/traces/20261007-105246_64123475_turn01_aef6735b.jsonl` |
| **Trường hợp B: Đổi tên file chính sách (Mua từ 01/10/2026)** | *(Sau khi đổi tên file thành `cs-truoc-thang-10.md` & `cs-tu-thang-10.md`)*<br>*"Tôi mua ngày 02/10/2026, yêu cầu hoàn ngày 12/10/2026, chưa kích hoạt. Tôi có được hoàn không?"* | 1. Đọc `SKILL.md`.<br>2. Gọi `list_files("data/policies")` và tự động phát hiện tên file mới.<br>3. Đọc `data/policies/cs-tu-thang-10.md`.<br>4. Tính số ngày: $12/10 - 02/10 = 10$ ngày.<br>5. Đối chiếu điều kiện mới (hạn 14 ngày, phí 0%). | **Đủ điều kiện hoàn tiền**.<br>- Chính sách: Từ tháng 10.<br>- Số ngày: 10 ngày.<br>- Lý do: Trong hạn 14 ngày (10 ≤ 14) & chưa kích hoạt.<br>- Phí hoàn tiền: 0% (miễn phí).<br>- Căn cứ: `data/policies/cs-tu-thang-10.md`. | `stage-02-skills/traces/20261007-105251_a6892a97_turn01_85a9173a.jsonl` |
| **Trường hợp C: Thiếu thông tin kích hoạt** | *"Tôi mua ngày 02/10/2026, muốn hoàn ngày 12/10/2026."* | 1. Đọc `SKILL.md`.<br>2. Kiểm tra bộ 3 thông tin bắt buộc: Ngày mua (có), Ngày hoàn (có), Kích hoạt (**thiếu**).<br>3. Không giả định, dừng lại hỏi người dùng. | **Hỏi lại người dùng**:<br>*"Bạn cho tôi biết thêm một thông tin bắt buộc: sản phẩm đã được kích hoạt hay chưa kích hoạt? Theo skill refund-policy, tôi cần đủ 3 thông tin..."* | `stage-02-skills/traces/20261007-105256_fcff7302_turn01_98a09cf4.jsonl` |

---

### 1.3. Trả lời câu hỏi lý thuyết & phân tích Block 1

#### Câu hỏi 1: Vì sao cần tool để tìm file và skill để hướng dẫn chọn chính sách?
1. **Vai trò của tool tìm file (`list_files`):**
   - **Tính thích ứng linh hoạt (Adaptability):** Trong môi trường thực tế, tài liệu lưu trữ thường xuyên thay đổi: file bị đổi tên, file mới được cập nhật theo quý/năm. Tool `list_files` đóng vai trò là "giác quan" để Agent chủ động thám hiểm cấu trúc thư mục hiện hành, tránh hoàn toàn việc đoán mò (hallucination) tên file.
2. **Vai trò của skill (`refund-policy`):**
   - **Đóng gói tri thức nghiệp vụ chuyên biệt (Domain Expertise):** Việc xác định chính sách áp dụng không được dựa vào ngày đặt câu hỏi mà phải căn cứ vào **ngày mua hàng**. Skill cung cấp một chuỗi nguyên tắc nghiệp vụ khắt khe: quy tắc đủ 3 trường thông tin, cách tính ngày lịch, quy định kích hoạt và cấu trúc phản hồi chuẩn hóa.
   - **Tối ưu Context Window (Progressive Disclosure):** Thay vì nạp toàn bộ các tài liệu chính sách cồng kềnh vào System Prompt làm tràn ngữ cảnh, System Prompt chỉ mang tóm tắt ngắn (Skill Catalog). Chỉ khi gặp tác vụ cần thiết, Agent mới đọc `SKILL.md` và các tài liệu tham chiếu liên quan.

#### Câu hỏi 2: Nếu agent chưa có tool tìm file, việc sửa prompt có giải quyết được yêu cầu đổi tên file không? Giải thích.
- **Trả lời:** **KHÔNG THỂ giải quyết được một cách bền vững và tổng quát.**
- **Giải thích:**
  - Nếu Agent chỉ có `read_file` mà không có `list_files`, Agent hoàn toàn bị "mù" trước hệ thống tệp tin.
  - Việc sửa prompt (ví dụ viết cứng vào prompt tên file mới `cs-tu-thang-10.md`) thực chất chỉ là hành vi **hardcode** tên file từ mã nguồn sang câu lệnh prompt. Ngay khi hệ sinh thái thay đổi tên file lần tiếp theo (ví dụ: `chinh-sach-v2.md`), Agent sẽ lập tức sụp đổ với lỗi `FILE_NOT_FOUND`.
  - Một Agent thông minh bắt buộc phải có tool để tự truy vấn và khám phá môi trường thay vì phụ thuộc vào việc con người phải can thiệp sửa prompt thủ công sau mỗi lần dữ liệu biến động.

---

# PHẦN 2: BÀI TẬP BLOCK 2 (STAGES 03 - 04)
## Phân tích khối lượng công việc và kiểm tra quá tải bằng Script Skill

### 2.1. Yêu cầu & Thiết kế cải tiến Script `check_csv.py` và Skill `csv-quality`

Trong Block 2, công cụ `skills/csv-quality/scripts/check_csv.py` được mở rộng để phân tích tải công việc và phát hiện nhân sự quá tải dựa trên dữ liệu công việc (`task_id`, `owner`, `hours`):

1. **Tham số dòng lệnh `--max-hours`**: Bắt buộc phải cung cấp ngưỡng giờ tối đa (số hữu hạn không âm). Nếu thiếu, script trả về `exit_code != 0` và in thông báo lỗi ra `stderr`.
2. **Quy tắc phân tích nghiệp vụ & Tính toán**:
   - `hours_by_owner`: Tổng số giờ của từng nhân sự, chỉ cộng các dòng hợp lệ.
   - `overloaded_owners`: Danh sách những người có tổng giờ **lớn hơn** `--max-hours` (`total_hours > max_hours`).
   - `excluded_rows`: Danh sách các dòng bị loại bỏ khỏi việc tính giờ kèm danh sách lý do:
     - `wrong_field_count`: Dòng sai số lượng cột.
     - `missing_task_id`: Cột `task_id` bị trống.
     - `duplicate_id`: Trùng lặp `task_id` với dòng đã xuất hiện trước đó trong file.
     - `missing_owner`: Cột `owner` bị trống.
     - `invalid_hours`: Cột `hours` không phải số thực hữu hạn không âm.
   - **Xử lý edge-case xuất hiện lần đầu bị lỗi giờ**: Nếu dòng đầu tiên của một `task_id` có `hours` không hợp lệ (ví dụ: `abc`), và dòng thứ hai trùng `task_id` đó: dòng 1 bị loại vì `invalid_hours`, dòng 2 bị loại vì `duplicate_id`. Cả hai đều không được tính giờ.
3. **Cập nhật Skill `csv-quality/SKILL.md`**:
   - Bắt buộc Agent kiểm tra xem câu hỏi có chứa thông tin ngưỡng giờ hay không.
   - Nếu **thiếu ngưỡng giờ**, Agent **phải dừng lại và hỏi người dùng**, tuyệt đối không tự giả định ngưỡng (không tự lấy 8 giờ) và không dùng ngưỡng từ ngữ cảnh trước.

---

### 2.2. Kiểm thử dữ liệu mẫu & Test Suite

File `data/workload.csv`:
```csv
task_id,owner,hours
T01,Lan,4
T02,Lan,5
T03,Minh,3
T04,Minh,abc
T02,Lan,5
T05,,2
```

- **Phân tích chi tiết từng dòng**:
  - Dòng 2 (`T01,Lan,4`): Hợp lệ $\rightarrow$ Lan: 4h.
  - Dòng 3 (`T02,Lan,5`): Hợp lệ $\rightarrow$ Lan: 5h (Tổng Lan = 9h).
  - Dòng 4 (`T03,Minh,3`): Hợp lệ $\rightarrow$ Minh: 3h.
  - Dòng 5 (`T04,Minh,abc`): Giờ không hợp lệ $\rightarrow$ Loại khỏi tổng giờ (`invalid_hours`).
  - Dòng 6 (`T02,Lan,5`): Trùng `T02` đã xuất hiện ở dòng 3 $\rightarrow$ Loại khỏi tổng giờ (`duplicate_id`).
  - Dòng 7 (`T05,,2`): Thiếu người phụ trách $\rightarrow$ Loại khỏi tổng giờ (`missing_owner`).
- **Tổng kết giờ**: Lan: 9h, Minh: 3h.
- **Ngưỡng 8 giờ**: Lan có 9h > 8h $\rightarrow$ Lan bị quá tải (+1h).
- **Ngưỡng 9 giờ**: Lan có 9h $\le$ 9h, Minh có 3h $\le$ 9h $\rightarrow$ Không có ai quá tải.

File `data/workload-edge.csv`:
```csv
task_id,owner,hours
E01,Lan,abc
E01,Lan,5
E02,Minh,0
```
- Dòng 2 (`E01,Lan,abc`): Bị loại vì `invalid_hours`.
- Dòng 3 (`E01,Lan,5`): Bị loại vì `duplicate_id` (trùng `E01`).
- Dòng 4 (`E02,Minh,0`): Hợp lệ $\rightarrow$ Minh: 0h. Lan: 0h.
- Kết quả: Không ai bị tính sai giờ dù dòng đầu tiên của `E01` bị lỗi cú pháp.

> **Unit tests**: 14/14 test cases trong `tests/test_check_csv.py` (bao gồm `test_edge_case_first_occurrence_invalid_hours`, `test_missing_or_invalid_max_hours`) đều đạt **PASS** 100%.

---

### 2.3. Bảng kết quả thực nghiệm các kịch bản Block 2 (Có đối chiếu Trace)

| Kịch bản | Yêu cầu của người dùng | Hành vi của Agent & Công cụ sử dụng | Kết luận & Trích dẫn trả lời | File Báo cáo Output | Trace File |
|---|---|---|---|---|---|
| **Kịch bản 1: Phân tích với ngưỡng 8 giờ** | *"Phân tích khối lượng công việc từ file data/workload.csv với ngưỡng tối đa 8 giờ và ghi báo cáo vào output/workload-report-8h.md."* | 1. Đọc `SKILL.md` của `csv-quality`.<br>2. Chạy `bash`: `python skills/csv-quality/scripts/check_csv.py --input data/workload.csv --max-hours 8`.<br>3. Nhận JSON thành công (exit 0).<br>4. Đọc `report-template.md`.<br>5. Ghi báo cáo bằng `write_file`. | **Lan bị quá tải (9 giờ > 8 giờ)**.<br>- Tổng giờ: Lan: 9h, Minh: 3h.<br>- 3 dòng bị loại: T04 (invalid_hours), T02 (duplicate_id), T05 (missing_owner).<br>- Khuyến nghị: Chuyển bớt việc từ Lan sang Minh, chuẩn hóa lại dữ liệu gốc. | `output/workload-report-8h.md` | `stage-04-script-skill/traces/20261007-153407_bee6ab3c_turn01_818adf21.jsonl` |
| **Kịch bản 2: Phân tích với ngưỡng 9 giờ** | *"Phân tích khối lượng công việc từ file data/workload.csv với ngưỡng tối đa 9 giờ và ghi báo cáo vào output/workload-report-9h.md."* | 1. Đọc `SKILL.md`.<br>2. Chạy `bash`: `python skills/csv-quality/scripts/check_csv.py --input data/workload.csv --max-hours 9`.<br>3. Nhận JSON phân tích (exit 0).<br>4. Đọc template và ghi báo cáo bằng `write_file`. | **Không ai bị quá tải**.<br>- Tổng giờ: Lan: 9h (vừa đúng ngưỡng), Minh: 3h.<br>- Dữ liệu có 3 dòng lỗi bị loại bỏ tương tự kịch bản 1. | `output/workload-report-9h.md` | `stage-04-script-skill/traces/20261007-153415_114d2c5e_turn01_25148080.jsonl` |
| **Kịch bản 3: Thiếu ngưỡng giờ** | *"Phân tích khối lượng công việc từ file data/workload.csv và ghi báo cáo vào output/workload-report-notarget.md."* | 1. Đọc `SKILL.md`.<br>2. Phát hiện người dùng chưa cung cấp `--max-hours`.<br>3. Không tự tiện chạy script với giá trị đoán.<br>4. Dừng lại hỏi người dùng. | **Dừng lại hỏi ngưỡng giờ**:<br>*"Theo skill, phân tích quá tải/tính tổng giờ theo ngưỡng bắt buộc phải có --max-hours, và tôi không được tự giả định ngưỡng. Bạn chưa cung cấp ngưỡng giờ tối đa. Vui lòng cho biết ngưỡng giờ tối đa mỗi người (ví dụ 8 giờ/tuần)?"* | *(Không ghi file)* | `stage-04-script-skill/traces/20261007-153422_223b4ead_turn01_97bb56e0.jsonl` |
| **Kịch bản 4: File không tồn tại (Lỗi thực thi)** | *"Phân tích khối lượng công việc từ file data/khong-co.csv với ngưỡng 8 giờ và ghi báo cáo vào output/workload-khongco.md."* | 1. Đọc `SKILL.md`.<br>2. Chạy `bash`: `python skills/csv-quality/scripts/check_csv.py --input data/khong-co.csv --max-hours 8`.<br>3. Script trả về `exit_code: 1` và `stderr: "ERROR: Không đọc được file data/khong-co.csv: No such file or directory"`.<br>4. Agent phát hiện lỗi thực thi, tuân thủ không bịa báo cáo. | **Báo lỗi thực thi, từ chối tạo báo cáo giả**:<br>*"Script check_csv.py đã báo lỗi (exit_code 1): ERROR: Không đọc được file data/khong-co.csv... Tôi chưa ghi báo cáo vào output/workload-khongco.md — theo quy tắc của skill, không được tạo báo cáo như thể đã phân tích thành công."* | *(Không ghi file)* | `stage-04-script-skill/traces/20261007-153424_f76839b1_turn01_4e9e1b15.jsonl` |

---

### 2.4. Trả lời câu hỏi lý thuyết & phân tích Block 2

#### Câu hỏi 1: Trong luồng xử lý của bài này, phần nào do script tính toán và phần nào do model diễn giải? Vì sao không để model tự cộng giờ trực tiếp từ CSV?

1. **Phần do Script tính toán:**
   - **Xác thực dữ liệu (Data Validation):** Kiểm tra cấu trúc dòng CSV, parse định dạng số thực hữu hạn không âm cho cột `hours`, phát hiện trường trống (`missing_owner`, `missing_task_id`).
   - **Phát hiện trùng lặp có trạng thái (Stateful Deduplication):** Lưu trữ tập hợp các `task_id` đã xuất hiện để đánh dấu dòng trùng lặp (`duplicate_id`).
   - **Tính toán số học & So sánh logic:** Tính tổng giờ lũy kế cho từng nhân sự (`hours_by_owner`), phân loại dòng bị loại (`excluded_rows`), và so sánh số học tuyệt đối với ngưỡng (`total_hours > max_hours`) để xác định danh sách quá tải (`overloaded_owners`).
2. **Phần do Model diễn giải:**
   - **Hiểu ý định người dùng (Intent Understanding):** Phân tích câu hỏi, trích xuất đường dẫn file, trích xuất ngưỡng giờ và đường dẫn báo cáo đầu ra.
   - **Điều phối công cụ (Tool Orchestration):** Quyết định thứ tự thực thi: đọc tài liệu skill $\rightarrow$ kiểm tra đủ tham số $\rightarrow$ gọi bash chạy script $\rightarrow$ đọc template mẫu $\rightarrow$ ghi file báo cáo.
   - **Tổng hợp ngôn ngữ tự nhiên & Khuyến nghị (Synthesis & Reasoning):** Diễn giải kết quả phân tích JSON thành báo cáo Markdown rõ ràng, phân tích mức độ tin cậy của dữ liệu khi có dòng lỗi, và đưa ra khuyến nghị quản lý nhân sự (ví dụ: điều chuyển công việc giữa Lan và Minh).
3. **Vì sao không để Model tự cộng giờ trực tiếp từ CSV?**
   - **Điểm yếu cố hữu của LLM về số học chính xác:** LLM là mô hình dự đoán token xác suất, rất dễ tính sai số học, sót dòng khi file CSV có nhiều dữ liệu hoặc bị "ảo giác" (hallucination) khi gặp định dạng lỗi như chuỗi `"abc"` hay số âm.
   - **Chi phí Token và Ngữ cảnh:** Đưa toàn bộ file CSV lớn vào context window của model gây tốn chi phí và lãng phí bộ nhớ. Trong khi đó, việc chuyển giao tính toán cho một Python script chỉ tốn vài millisecond và đảm bảo tính chính xác tuyệt đối 100%.
   - **Nguyên tắc "Script-backed Skills":** Tách biệt rõ ràng giữa *bộ não điều phối/ngôn ngữ* (LLM) và *động cơ tính toán tất định* (Code/Script).

#### Câu hỏi 2: Nếu sửa logic trong script (ví dụ đổi cách tính giờ hoặc đổi cấu trúc JSON kết quả) mà không cập nhật SKILL.md và file reference, điều gì sẽ xảy ra ở tầng agent? Nêu cụ thể những điểm có thể sai lệch hoặc thiếu sót.

Khi logic trong script thay đổi mà không đồng bộ cập nhật `SKILL.md` và `references/report-template.md`, ở tầng Agent sẽ phát sinh các lỗi nghiêm trọng sau:

1. **Sai lệch tham số dòng lệnh hoặc lỗi gọi script:**
   - Nếu script đổi tên tham số (ví dụ từ `--max-hours` thành `--threshold` hoặc `--limit`), Agent vẫn tiếp tục đọc hướng dẫn cũ trong `SKILL.md` và gọi lệnh có cú pháp cũ. Hậu quả là script báo lỗi `unrecognized arguments` (`exit_code != 0`), khiến Agent không thể hoàn thành tác vụ.
2. **Đứt gãy liên kết dữ liệu trong Báo cáo (Key Mismatch / Hallucination):**
   - Nếu script đổi cấu trúc JSON đầu ra (ví dụ: đổi trường `overloaded_owners` thành `overloaded_list`, hoặc đổi cấu trúc từ mảng sang dictionary), nhưng file `report-template.md` vẫn giữ quy ước cũ, Agent sẽ không tìm thấy key cần thiết trong JSON. Khi đó, Agent có nguy cơ:
     - Để trống thông tin hoặc báo `None`/`N/A`.
     - Tệ hơn là Agent tự "suy đoán" và tự điền con số theo trí tưởng tượng (hallucination), làm mất tính trung thực của báo cáo.
3. **Mâu thuẫn logic và đánh giá sai nghiệp vụ:**
   - Nếu script thay đổi quy tắc tính toán (ví dụ: tính ngưỡng là $\ge$ thay vì $>$ hoặc thay đổi cơ chế xử lý dòng trùng lặp), nhưng `SKILL.md` vẫn mô tả logic cũ, Agent khi viết phần "Đánh giá & Khuyến nghị" sẽ đưa ra những giải thích mâu thuẫn trực tiếp với các con số mà script đã tính toán, làm người dùng bối rối và mất độ tin cậy vào hệ thống.
4. **Vi phạm nguyên tắc Single Source of Truth:**
   - Skill và Script là một thể thống nhất trong kiến trúc Agent. Script là phần thực thi (`backend engine`), còn Skill & Reference là giao diện định nghĩa hợp đồng API và hướng dẫn sử dụng (`API contract & documentation`). Khi hợp đồng không đồng bộ với mã nguồn thực tế, toàn bộ hệ thống Agentic sẽ bị gãy vỡ tính nhất quán.

---

# TỔNG KẾT & KẾT LUẬN

1. Toàn bộ các yêu cầu của cả **Block 1** và **Block 2** đã được cài đặt hoàn chỉnh, kiểm thử nghiêm ngặt qua unit test và chạy thực nghiệm trực tiếp với mô hình DeepSeek LLM.
2. Tất cả các file trace JSONL trong các thư mục `stage-02-skills/traces/` và `stage-04-script-skill/traces/` đã được lưu trữ đầy đủ, minh chứng cho toàn bộ hành vi thực tế của Agent trong các trường hợp bình thường, trường hợp đổi tên file, trường hợp thiếu thông tin và trường hợp lỗi thực thi.
3. Không có bất kỳ giá trị ngưỡng hay kết quả nào bị hardcode trong mã nguồn hoặc prompt. Dự án đã được dọn dẹp sạch sẽ các tệp tin tạm và sẵn sàng để đóng gói nộp bài.
