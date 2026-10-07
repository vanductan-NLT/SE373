---
name: refund-policy
description: Tra cứu và áp dụng chính sách hoàn tiền cho khách hàng dựa trên ngày mua và ngày yêu cầu hoàn tiền. Dùng khi người dùng hỏi về hoàn tiền, trả hàng, chính sách refund hoặc kiểm tra điều kiện hoàn tiền đơn hàng.
---

# Refund Policy Skill

Hướng dẫn kiểm tra điều kiện và áp dụng chính sách hoàn tiền theo ngày mua của khách hàng.

## Nguyên tắc xử lý

1. **Kiểm tra thông tin đầu vào (Bắt buộc)**:
   Để đưa ra kết luận, bắt buộc phải có đầy đủ 3 thông tin sau:
   - **Ngày mua hàng** (ví dụ: 2026-09-28 hoặc 28/09/2026).
   - **Ngày yêu cầu hoàn tiền** (ví dụ: 2026-10-06 hoặc 06/10/2026).
   - **Trạng thái kích hoạt của sản phẩm** (đã kích hoạt hay chưa kích hoạt).
   
   ⚠️ **Nếu thiếu bất kỳ thông tin nào trong 3 thông tin trên** (ví dụ: người dùng chưa nêu rõ sản phẩm đã kích hoạt hay chưa), **phải hỏi lại người dùng để làm rõ, tuyệt đối không tự giả định hay phỏng đoán**.

2. **Tìm tài liệu bằng tool `list_files`**:
   - Không được giả định trước tên file chính sách cố định.
   - Luôn sử dụng tool `list_files` với đường dẫn `data/policies` để tìm tất cả các file tài liệu chính sách hiện có trong thư mục.
   - Sau khi có danh sách file, dùng tool `read_file` để đọc nội dung từng tài liệu chính sách.

3. **Chọn chính sách theo ngày mua**:
   - Đọc kỹ phạm vi hiệu lực của từng file chính sách.
   - So sánh với **ngày mua** của khách hàng để chọn chính sách áp dụng thích hợp (không chọn theo ngày yêu cầu hoàn).

4. **Cách tính số ngày**:
   - Số ngày đã qua = Ngày yêu cầu hoàn tiền − Ngày mua (tính theo số ngày lịch).
   - Sử dụng ngày yêu cầu hoàn tiền do người dùng cung cấp trong câu hỏi, không dùng ngày hiện tại của máy tính.
   - Nếu số ngày đã qua nhỏ hơn hoặc bằng đúng giới hạn số ngày quy định trong chính sách thì vẫn đủ điều kiện về thời gian.

5. **Quy định kích hoạt và phí hoàn tiền**:
   - Nếu sản phẩm đã kích hoạt, không được hoàn tiền theo bất kỳ chính sách nào.
   - Nếu đủ điều kiện hoàn tiền, áp dụng mức phí (hoặc miễn phí) theo đúng văn bản chính sách đã chọn.

6. **Mẫu câu trả lời**:
   - Đọc mẫu trả lời tại `skills/refund-policy/references/answer-template.md` bằng `read_file` nếu cần tham khảo.
   - Câu trả lời gửi người dùng phải nêu đầy đủ: chính sách áp dụng, số ngày đã qua, kết luận đủ/không đủ điều kiện, phí hoàn tiền nếu đủ, và đường dẫn tương đối của tài liệu làm căn cứ.

## Các bước thực hiện

1. Xem xét câu hỏi của người dùng để xác định 3 thông tin: Ngày mua, Ngày yêu cầu hoàn, Trạng thái kích hoạt. Nếu thiếu, đặt câu hỏi yêu cầu người dùng bổ sung.
2. Gọi `list_files(path="data/policies")` để lấy danh sách các file chính sách.
3. Gọi `read_file(path="data/policies/<tên-file>")` cho các file chính sách để nắm rõ phạm vi áp dụng theo ngày mua.
4. Đối chiếu ngày mua của khách hàng để xác định chính sách áp dụng tương ứng.
5. Tính chênh lệch số ngày giữa ngày yêu cầu hoàn và ngày mua. So sánh với giới hạn ngày trong chính sách và kiểm tra trạng thái kích hoạt.
6. Trả lời người dùng theo đúng cấu trúc chuẩn được quy định tại `skills/refund-policy/references/answer-template.md`.
