# Báo cáo phân tích công việc & kiểm tra quá tải: `data/workload.csv`

Công cụ: `skills/csv-quality/scripts/check_csv.py` | Ngưỡng giờ quy định: 8 giờ

## 1. Kết quả kiểm tra quá tải
- **Ngưỡng tối đa cho phép**: 8 giờ
- **Danh sách nhân sự quá tải**:
| Nhân sự | Tổng giờ thực tế | Đánh giá |
|---|---|---|
| Lan | 9 | Vượt ngưỡng (+1 giờ) |

- **Tổng giờ làm việc theo nhân sự**:
| Nhân sự | Tổng giờ | Đánh giá |
|---|---|---|
| Lan | 9 | Quá tải |
| Minh | 3 | Bình thường |

## 2. Các dòng bị loại khỏi tổng giờ
| Dòng | Task ID | Lý do loại bỏ |
|---|---|---|
| 5 | T04 | invalid_hours |
| 6 | T02 | duplicate_id |
| 7 | T05 | missing_owner |

## 3. Thống kê chất lượng dữ liệu
| Chỉ số | Giá trị |
|---|---|
| Tổng số dòng dữ liệu (không tính header) | 6 |
| Số dòng thiếu owner | 1 |
| Số dòng hours không hợp lệ | 1 |
| Số task_id bị lặp (distinct) | 1 (T02) |

## 4. Đánh giá & Khuyến nghị
- **Đánh giá**: Dữ liệu có chất lượng chưa cao: 3/6 dòng bị loại khỏi tổng giờ do lỗi (hours không hợp lệ "abc", task_id T02 bị lặp, owner trống). Sau khi loại lỗi, chỉ còn Lan (9 giờ) và Minh (3 giờ). Lan vượt ngưỡng 8 giờ nên đang quá tải, tuy nhiên con số này dựa trên dữ liệu đã lọc nên cần sửa lỗi để có kết luận chính xác.
- **Khuyến nghị**: Sửa các dòng lỗi trước khi kết luận cuối cùng — nhập lại hours hợp lệ cho T04, xử lý task_id T02 bị trùng (dòng 3 và dòng 6), và bổ sung owner cho T05. Sau đó chạy lại phân tích. Cân đối lại khối lượng cho Lan: hiện vượt ngưỡng, có thể chuyển bớt công việc sang Minh (mới 3 giờ) để đưa Lan về dưới 8 giờ.
