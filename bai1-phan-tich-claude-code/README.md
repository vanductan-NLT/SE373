# BTVN#1 · Phân tích hệ thống AI đang dùng: Claude Code

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11

Bài làm: [BTVN1_Phan_tich_Claude_Code.pdf](BTVN1_Phan_tich_Claude_Code.pdf)

Nội dung gồm 3 phần:

1. **Phân loại hệ thống** theo 3 tiêu chí (ai quyết định bước tiếp theo, ai giữ trạng thái, ai dừng vòng lặp) → Claude Code là một Agent.
2. **Phân tích một failure mode**: thiếu bước xác minh (verification failure) — agent đọc log test thấy nhiều chữ "PASSED" rồi báo xong dù vẫn còn 2 test fail.
3. **Hai lớp harness**: lớp *tools* (tool có schema, harness kiểm tra trước khi thực thi) và lớp *permission* (giới hạn thư mục làm việc, cần người duyệt với lệnh có tác động lớn).
