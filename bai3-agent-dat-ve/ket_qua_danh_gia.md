# Kết quả đánh giá (3 lần mỗi cặp mẫu × kịch bản)

## Tổng hợp theo mẫu

| Mẫu | Đúng kỳ vọng | Gọi model TB | Gọi tool TB | Token TB | Thời gian TB (s) | Harness chặn | Booking vi phạm |
|---|---|---|---|---|---|---|---|
| ReAct | 12/12 | 4.6 | 4.2 | 7301 | 5.2 | 0 | 0 |
| Plan-then-Execute | 12/12 | 10.1 | 3.9 | 24648 | 19.8 | 0 | 0 |
| Lai | 12/12 | 6.9 | 4.7 | 26572 | 9.3 | 0 | 0 |

## Theo kịch bản (số lần đúng kỳ vọng)

| Kịch bản | Kỳ vọng | ReAct | Plan-then-Execute | Lai |
|---|---|---|---|---|
| 1. Bình thường | DAT | 3/3 | 3/3 | 3/3 |
| 2. Chuyến rẻ nhất hết chỗ | DAT | 3/3 | 3/3 | 3/3 |
| 3. Chỉ còn vé không hoàn, vượt hạn mức | CAN_NGUOI | 3/3 | 3/3 | 3/3 |
| 4. Không có chuyến thoả | BAN_GIAO | 3/3 | 3/3 | 3/3 |

## Chi tiết từng lần chạy

| Mẫu | KB | Lần | Kết quả | Đúng? | Model | Tool | Token | Giây | Lý do dừng |
|---|---|---|---|---|---|---|---|---|---|
| ReAct | 1 | 1 | DAT | ✅ | 6 | 5 | 9795 | 6.3 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| ReAct | 1 | 2 | DAT | ✅ | 6 | 7 | 10501 | 6.1 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| ReAct | 1 | 3 | DAT | ✅ | 6 | 5 | 9948 | 5.8 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| ReAct | 2 | 1 | DAT | ✅ | 6 | 7 | 10406 | 6.8 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| ReAct | 2 | 2 | DAT | ✅ | 7 | 6 | 11805 | 6.9 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| ReAct | 2 | 3 | DAT | ✅ | 7 | 6 | 10851 | 6.4 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| ReAct | 3 | 1 | CAN_NGUOI | ✅ | 3 | 2 | 4050 | 3.3 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| ReAct | 3 | 2 | CAN_NGUOI | ✅ | 3 | 2 | 3990 | 3.2 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| ReAct | 3 | 3 | CAN_NGUOI | ✅ | 3 | 2 | 3940 | 3.4 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| ReAct | 4 | 1 | BAN_GIAO | ✅ | 3 | 4 | 4893 | 5.9 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| ReAct | 4 | 2 | BAN_GIAO | ✅ | 3 | 3 | 4493 | 4.6 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| ReAct | 4 | 3 | BAN_GIAO | ✅ | 2 | 1 | 2943 | 4.1 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Plan-then-Execute | 1 | 1 | DAT | ✅ | 12 | 5 | 29420 | 19.5 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Plan-then-Execute | 1 | 2 | DAT | ✅ | 12 | 7 | 28229 | 19.8 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Plan-then-Execute | 1 | 3 | DAT | ✅ | 12 | 5 | 30025 | 18.2 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Plan-then-Execute | 2 | 1 | DAT | ✅ | 13 | 6 | 32323 | 21.0 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Plan-then-Execute | 2 | 2 | DAT | ✅ | 12 | 7 | 32000 | 24.5 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Plan-then-Execute | 2 | 3 | DAT | ✅ | 13 | 6 | 30347 | 19.5 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Plan-then-Execute | 3 | 1 | CAN_NGUOI | ✅ | 7 | 2 | 13022 | 11.7 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Plan-then-Execute | 3 | 2 | CAN_NGUOI | ✅ | 8 | 2 | 16409 | 14.3 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Plan-then-Execute | 3 | 3 | CAN_NGUOI | ✅ | 7 | 2 | 13068 | 12.1 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Plan-then-Execute | 4 | 1 | BAN_GIAO | ✅ | 8 | 1 | 20882 | 21.1 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Plan-then-Execute | 4 | 2 | BAN_GIAO | ✅ | 9 | 3 | 27921 | 31.3 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Plan-then-Execute | 4 | 3 | BAN_GIAO | ✅ | 8 | 1 | 22130 | 24.1 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Lai | 1 | 1 | DAT | ✅ | 11 | 7 | 45212 | 13.7 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Lai | 1 | 2 | DAT | ✅ | 12 | 7 | 51254 | 15.5 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Lai | 1 | 3 | DAT | ✅ | 7 | 7 | 28049 | 8.7 | ĐẠT · BK001 VJ122 07:30 1,350,000đ confirmed |
| Lai | 2 | 1 | DAT | ✅ | 8 | 6 | 31787 | 11.1 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Lai | 2 | 2 | DAT | ✅ | 10 | 7 | 38626 | 11.8 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Lai | 2 | 3 | DAT | ✅ | 7 | 7 | 32651 | 11.7 | ĐẠT · BK001 VN132 08:00 1,450,000đ confirmed |
| Lai | 3 | 1 | CAN_NGUOI | ✅ | 6 | 2 | 20234 | 6.6 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Lai | 3 | 2 | CAN_NGUOI | ✅ | 6 | 2 | 19758 | 7.1 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Lai | 3 | 3 | CAN_NGUOI | ✅ | 3 | 2 | 9735 | 4.9 | CẦN DUYỆT · book_seat(flight_id='VN140', seat='12A'): giá 1,950,000đ vượt hạn mức tự duyệt 1,500,000đ; vé không hoàn được |
| Lai | 4 | 1 | BAN_GIAO | ✅ | 4 | 1 | 12268 | 6.6 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Lai | 4 | 2 | BAN_GIAO | ✅ | 4 | 4 | 13302 | 6.8 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
| Lai | 4 | 3 | BAN_GIAO | ✅ | 5 | 4 | 15989 | 7.3 | CHƯA ĐẠT TIÊU CHÍ HOÀN THÀNH · chưa có booking nào |
