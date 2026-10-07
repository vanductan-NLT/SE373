# Báo cáo phân tích công việc & kiểm tra quá tải: `data/workload.csv`

Công cụ: `skills/csv-quality/scripts/check_csv.py` | Ngưỡng giờ quy định: 9 giờ

## 1. Kết quả kiểm tra quá tải
- **Ngưỡng tối đa cho phép**: 9 giờ
- **Danh sách nhân sự quá tải**:
| Nhân sự | Tổng giờ thực tế | Đánh giá |
|---|---|---|
| — | — | — |
Không có nhân sự nào vượt ngưỡng 9 giờ.

- **Tổng giờ làm việc theo nhân sự**:
| Nhân sự | Tổng giờ | Đánh giá |
|---|---|---|
| Lan | 9 | Bình thường (đúng ngưỡng) |
| Minh | 3 | Bình thường |

## 2. Các dòng bị loại khỏi tổng giờ
| Dòng | Task ID | Lý do loại bỏ |
|---|---|---|
| 5 | T04 | hours không hợp lệ ('abc') |
| 6 | T02 | task_id bị lặp (đã xuất hiện ở dòng 3) |
| 7 | T05 | thiếu owner |

## 3. Thống kê chất lượng dữ liệu
| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng dữ liệu (không tính header) | 6 |
| Số dòng thiếu owner | 1 |
| Số dòng hours không hợp lệ | 1 |
| Số task_id bị lặp (distinct) | 1 (T02) |

## 4. Đánh giá & Khuyến nghị
- **Đánh giá**: Không có nhân sự nào vượt ngưỡng 9 giờ; Lan đạt đúng ngưỡng (9 giờ). Tuy nhiên dữ liệu đầu vào chưa sạch: 3/6 dòng bị loại (1 dòng hours không hợp lệ, 1 dòng trùng task_id, 1 dòng thiếu owner), nên tổng giờ thực tế có thể cao hơn con số báo cáo — độ tin cậy dữ liệu ở mức trung bình.
- **Khuyến nghị**: Sửa dữ liệu gốc — nhập lại giá trị số cho hours của T04, loại bỏ hoặc đổi task_id trùng của T02, và bổ sung owner cho T05; sau đó chạy lại phân tích. Nếu T04 có giờ hợp lệ, cần kiểm tra lại vì tổng giờ của Minh có thể tăng và ảnh hưởng kết luận quá tải.
