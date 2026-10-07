---
name: csv-quality
description: Kiểm tra chất lượng file CSV công việc (task_id, owner, hours), tính tổng giờ làm việc theo từng người và phát hiện nhân sự bị quá tải dựa trên ngưỡng giờ (max-hours) bằng script có sẵn, rồi ghi báo cáo Markdown dưới output/. Dùng khi người dùng yêu cầu kiểm tra chất lượng dữ liệu CSV, tính tổng giờ theo người hoặc rà soát nhân sự quá tải.
---

# CSV Quality & Workload Analysis

Kiểm tra chất lượng CSV công việc và phân tích quá tải lao động bằng script `check_csv.py`, không tự tính toán thủ công.

## Quy tắc thực hiện

1. **Kiểm tra thông tin ngưỡng giờ (`max-hours`)**:
   - Khi người dùng yêu cầu phân tích quá tải hoặc tính tổng giờ theo ngưỡng: **Bắt buộc phải có ngưỡng giờ tối đa (`--max-hours`)**.
   - ⚠️ **Nếu người dùng chưa cung cấp ngưỡng giờ cụ thể**: Dừng lại và **hỏi người dùng ngưỡng giờ tối đa là bao nhiêu** trước khi thực thi. Tuyệt đối không tự giả định ngưỡng (ví dụ không tự chọn 8 giờ) và không dùng ngưỡng từ các lượt chat trước.

2. **Chạy script phân tích**:
   Dùng tool `bash` (cwd là workspace). Lệnh đầy đủ:
   ```bash
   python skills/csv-quality/scripts/check_csv.py --input <đường dẫn CSV> --max-hours <ngưỡng>
   ```
   Ví dụ:
   ```bash
   python skills/csv-quality/scripts/check_csv.py --input data/workload.csv --max-hours 8
   ```

3. **Kiểm tra kết quả**:
   - `exit_code` 0: Phân tích thành công. Đọc kết quả JSON từ `stdout` gồm: `max_hours`, `row_count`, `hours_by_owner`, `overloaded_owners`, `excluded_rows`, `issues`. Dữ liệu có dòng lỗi hoặc có người quá tải vẫn là exit 0.
   - `exit_code` khác 0: **Lỗi thực thi** (file không tồn tại, thiếu cột bắt buộc, cú pháp CSV lỗi, thiếu hoặc sai tham số `--max-hours`). Đọc `stderr`, báo lỗi rõ ràng cho người dùng. Không bịa thống kê, không ghi báo cáo như thể đã phân tích thành công.

4. **Viết báo cáo**:
   - Đọc template tại `skills/csv-quality/references/report-template.md` bằng `read_file`.
   - Điền đầy đủ các thông tin:
     + Ngưỡng giờ quy định (`max_hours`)
     + Thống kê chất lượng dữ liệu
     + Tổng giờ làm việc theo từng nhân sự (`hours_by_owner`)
     + Danh sách nhân sự quá tải (`overloaded_owners`)
     + Danh sách các dòng bị loại khỏi tổng giờ kèm lý do (`excluded_rows`)
   - Ghi báo cáo bằng `write_file` vào đường dẫn yêu cầu (mặc định `output/workload.md` hoặc `output/csv-quality.md`).
   - Trả lời người dùng: đường dẫn file đã ghi và tóm tắt ngắn gọn kết luận.
