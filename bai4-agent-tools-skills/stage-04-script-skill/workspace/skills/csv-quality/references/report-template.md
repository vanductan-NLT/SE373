# Báo cáo phân tích công việc & kiểm tra quá tải: `{đường dẫn CSV}`

Công cụ: `skills/csv-quality/scripts/check_csv.py` | Ngưỡng giờ quy định: {max_hours} giờ

## 1. Kết quả kiểm tra quá tải
- **Ngưỡng tối đa cho phép**: {max_hours} giờ
- **Danh sách nhân sự quá tải**:
| Nhân sự | Tổng giờ thực tế | Đánh giá |
|---|---|---|
| {owner} | {total_hours} | Vượt ngưỡng (+{over_hours} giờ) |
*(Nếu không có ai quá tải: Không có nhân sự nào vượt ngưỡng {max_hours} giờ).*

- **Tổng giờ làm việc theo nhân sự**:
| Nhân sự | Tổng giờ | Đánh giá |
|---|---|---|
| {owner} | {total_hours} | {Quá tải / Bình thường} |

## 2. Các dòng bị loại khỏi tổng giờ
| Dòng | Task ID | Lý do loại bỏ |
|---|---|---|
| {line} | {task_id} | {reasons} |

## 3. Thống kê chất lượng dữ liệu
| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng dữ liệu (không tính header) | {row_count} |
| Số dòng thiếu owner | {missing_owner_count} |
| Số dòng hours không hợp lệ | {invalid_hours_count} |
| Số task_id bị lặp (distinct) | {duplicate_id_count} ({duplicate_ids}) |

## 4. Đánh giá & Khuyến nghị
- **Đánh giá**: {Nhận xét tổng thể về độ tin cậy của dữ liệu và tình trạng quá tải nhân sự}
- **Khuyến nghị**: {Khuyến nghị khắc phục các dòng lỗi và cân đối lại khối lượng công việc}
