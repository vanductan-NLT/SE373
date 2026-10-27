# BTVN#6 · Challenge B: Context management — Ghi chú thiết kế chi tiết

> Báo cáo nộp cho thầy là **`BAO_CAO.pdf`** (ngắn, nhiều ảnh output thật). File này là bản chi tiết để tra cứu và chuẩn bị vấn đáp.

**Sinh viên:** Văn Đức Tân · **MSSV:** 24521586 · **Lớp:** SE373.R11 · **Nhóm:** 15 · **Nộp:** 27/10/2026
**Code:** thư mục `bai6-context-management/` (file zip kèm theo). **Căn cứ:** Slide Buổi 7 (Memory, context engineering and prompt caching), tr. 18-34.

## 1. Đề và phạm vi

Mục tiêu (Slide Buổi 7, tr. 32): giữ context nhỏ gọn mà agent vẫn làm đúng việc.

| | Yêu cầu | Trạng thái |
|---|---|---|
| **B1 Compact** (bắt buộc) | Session dài được compact; agent vẫn nhớ lỗi đang điều tra, cách đã thử, bước tiếp | Đã làm, PASS |
| **B2 Code Mode** (điểm cộng) | Agent trả lời câu hỏi trên nhiều file log; raw log không đi vào context | Đã làm, PASS |

Môi trường: LangChain v1 `create_agent`, model DeepSeek `deepseek-flash` (thinking mode) qua `ChatOpenAI`; nền lấy từ agent bài 5 (middleware giới hạn vòng lặp, file tools) và ý tưởng subprocess/timeout/env tối thiểu của bài 4. Mọi số token trong báo cáo là `usage` do API trả về (không tự ước lượng), lấy từ `demo-b1.txt`, `demo-b2.txt` và `traces/*.jsonl`.

## 2. Thiết kế B1: Compact

### 2.1 Session dài có log lớn được tạo thế nào (gợi ý 1, tr. 33)

Kịch bản giả, sinh deterministic (`random.Random`, seed 373): "API `POST /checkout` thỉnh thoảng trả HTTP 500" (`tools/debug_tools.py`).

| Tool | Output | Nhiễu |
|---|---|---|
| `read_log("checkout-api.log")` | 380 dòng, 33.602 ký tự | 159 dòng là `Retrying connection to db...` lặp; 14 dòng lỗi thật `DBPoolExhaustedError` (500); 2 dòng `ValidationError` (400, không liên quan); WARN slow query |
| `read_log("db-pool.log")`, `read_log("payment-gateway.log")` | 360 / 340 dòng, ~28.000 ký tự | Dòng `stats`, `recycled` lặp; bằng chứng `connection held by payment_client.charge for 10s`, `upstream timeout` |
| `run_tests()` | 366 dòng, 25.549 ký tự | 200 dòng PASSED, log khởi động lặp, 3 FAILED kèm traceback ~30 dòng |
| `apply_fix(mô tả)` | 1 dòng | Fix sai (tăng timeout / pool size) thì test vẫn fail; fix đúng (giải phóng kết nối DB trước khi gọi payment gateway) thì 203 passed |

Phiên demo (`run_demo_b1.py`) gồm 5 lượt user cố định: T1 nêu mục tiêu + hai ràng buộc ("KHÔNG đổi API công khai /checkout", "KHÔNG restart production") và đọc `checkout-api.log`; T2 chạy test; T3 thử fix sai "tăng timeout lên 30 giây" rồi chạy lại test; T4, T5 đọc thêm hai log. Sau đó lượt **HỎI LẠI** (đang điều tra gì / đã thử gì / ràng buộc / bước tiếp) và lượt **LÀM TIẾP** (áp fix đúng rồi chạy lại test: kiểm chứng checkpoint bằng cách cho agent tiếp tục task, tr. 22).

### 2.2 Khi nào kích hoạt compact (gợi ý 2, tr. 25-26)

`CompactionMiddleware.before_model` chạy trước **mỗi** lần gọi model. Bước "Observe token budget": lấy `usage_metadata` (input + output) của `AIMessage` gần nhất, cộng ước lượng ký tự/4 cho phần mới thêm sau nó (ToolMessage vừa về mà model chưa nhìn thấy). Chưa có usage thì ước lượng toàn bộ. Vượt `COMPACT_TRIGGER_TOKENS` thì compact; không đợi context đầy (tr. 25).

Ngưỡng demo là **20.000 token**, cố ý nhỏ để chắc chắn kích hoạt. Trong thực tế đặt khoảng 60-70% context window của model. Lần chạy B2 cho thấy model này nhận được context hơn 412.000 token, nên ngưỡng 20.000 ở đây chỉ phục vụ demo, không phải khuyến nghị.

### 2.3 Giữ gì, bỏ gì (gợi ý 3, Selective compaction, tr. 23)

| Slide | Áp vào code |
|---|---|
| **KEEP**: quyết định, lỗi chưa giải quyết, yêu cầu bắt buộc | Trường `constraints`, `findings`, `next_action` của checkpoint; prompt tạo checkpoint dặn ghi đủ ràng buộc user kể cả ràng buộc nói ở lượt đầu |
| **TRUNCATE**: output dài rút còn vài dòng lỗi chính | `pruning.py`: ToolMessage dài hơn 1.500 ký tự chỉ giữ dòng `ERROR/FATAL/FAILED/Traceback/E   .../XxxError:` (gộp trùng, đếm số lần) và dòng tổng kết. `checkout-api.log` 33.602 → 934 ký tự; output `run_tests` 25.549 → 1.303 ký tự, vẫn đủ 3 dòng FAILED và dòng `3 failed, 200 passed` |
| **DROP**: log trùng, thử nghiệm đã kết luận, dữ liệu dễ tái tạo | Dòng lặp gộp thành `(×159) ... Retrying connection ...`; thử nghiệm đã kết luận chỉ còn một dòng trong `failed_attempts` (đã thử gì + kết quả để khỏi thử lại); bản raw ghi ra `traces/archive/<id>.txt`, và tool deterministic nên gọi lại là có raw |

### 2.4 Pipeline (tr. 26)

| Bước slide | Cài đặt |
|---|---|
| Observe token budget | `measure_context_tokens` |
| Prune tool output | `pruning.prune_tool_output` + `archive_raw`, áp cho cả phần bị nén lẫn phần giữ lại (các ToolMessage dài) |
| Build checkpoint | LLM + structured output (Pydantic `Checkpoint`) |
| Reinject rules/plan | `create_agent` gắn lại system prompt ở mỗi lần gọi model nên system prompt không mất; phần cần lo là ràng buộc user nói giữa chat, đã đưa vào `constraints` |
| Resume & validate | `Checkpoint.missing_fields()` cảnh báo trường rỗng; demo hỏi lại và cho agent làm tiếp |

In ra `=== COMPACTED: <trước> → <sau> tokens ===` kèm nguyên văn checkpoint (xem `demo-b1.txt`).

### 2.5 Schema checkpoint (tr. 22)

Đủ 7 trường như slide: `goal, current_state, constraints, findings, failed_attempts, files, next_action`. Gọi LLM tạo checkpoint bằng `with_structured_output(Checkpoint, method="function_calling")`. DeepSeek ở thinking mode từ chối ép `tool_choice` ("Thinking mode does not support this tool_choice"), nên riêng lời gọi này dùng model tắt thinking (`build_model(thinking=False)`). Mọi trường có giá trị mặc định rỗng: model bỏ sót một trường thì vẫn dựng được checkpoint và `missing_fields()` báo trường đó (không làm chết cả phiên); lỗi khi tạo checkpoint được thử lại một lần.

### 2.6 Bẫy cặp `tool_call` / `ToolMessage` và hai bẫy liên quan

1. **ToolMessage mồ côi.** Mỗi `ToolMessage` phải đi sau `AIMessage.tool_calls` tương ứng, nếu không API báo lỗi 400. Đuôi giữ lại (K=4 message cuối) có thể bị cắt giữa cặp. `find_cutoff` lùi điểm cắt về tới khi gặp message không phải ToolMessage (Human, hoặc AI kèm `tool_calls` thì các ToolMessage của nó nằm trọn trong đuôi). `orphan_tool_messages` kiểm lại đuôi trước khi thay messages, có mồ côi thì không compact. `test_offline.py` thử mọi điểm cắt có thể của một session có cả gọi tool song song.
2. **Usage cũ.** Message AI nằm trong đuôi giữ lại mang `usage_metadata` của lần gọi *trước* khi nén; nếu để nguyên thì lần đo sau đọc nhầm số cũ (20.000+) và nén lại ngay. Nên bỏ `usage_metadata` của các message đuôi.
3. **Kết quả tool chưa được đọc.** Compact thường xảy ra ngay sau khi một ToolMessage lớn vừa về mà model chưa nhìn thấy, nên số đo phải cộng thêm ước lượng cho phần này (nếu chỉ đọc usage của lần gọi trước thì kích hoạt trễ một nhịp).
4. **Yêu cầu hiện tại của user rơi vào phần bị nén.** Điểm cắt tính theo số message nên có thể đẩy câu user vừa nói vào phần nén, chỉ còn lại bản LLM diễn đạt lại; checkpoint khi đó có thể ghi "chưa làm" trong khi đuôi giữ lại đã làm rồi. Cách xử lý: yêu cầu hiện tại nằm trong phần nén thì được ghi **nguyên văn** vào checkpoint (dòng `yêu cầu hiện tại của user`), và tiêu đề checkpoint dặn "các message ngay sau checkpoint mới hơn checkpoint, lệch thì theo chúng". Phát hiện nhờ review code độc lập, đã có test offline.
5. **Đầu chỉ còn checkpoint cũ.** Không có gì mới để nén thì không gọi LLM, nhưng vẫn rút gọn các tool output dài ở đuôi; nếu bỏ qua, một message AI gọi nhiều tool song song làm context phình mà không bao giờ nhỏ lại.

### 2.7 Vì sao tự viết, không dùng `SummarizationMiddleware` có sẵn

Bản có sẵn của LangChain tóm tắt tự do (bốn mục chung chung) và cắt theo số message. Đề và slide (tr. 20-23) yêu cầu structured checkpoint đủ trường + selective keep/drop theo loại nội dung. Chỉ học từ bản có sẵn cách thay messages (`RemoveMessage(REMOVE_ALL_MESSAGES)` + danh sách mới) và cách chọn điểm cắt an toàn; phần còn lại tự viết.

## 3. Thiết kế B2: Code Mode

- **Code chạy ở đâu (tr. 28):** LLM trả tool call `run_python(code)` kèm chương trình; **harness** (chương trình của mình) chạy nó trong một tiến trình Python riêng (`subprocess.run([sys.executable, "-c", code], ...)`, chạy thẳng interpreter, không qua bash để tránh lỗi Git Bash/WSL trên Windows). LLM không tự chạy gì, chỉ nhận lại phần chương trình `print`.
- **Giới hạn (tr. 31):** `cwd = workspace/`; timeout 15 giây (hết giờ thì dừng tiến trình, trả `timed_out`); env tối thiểu (`PATH`, `SYSTEMROOT`, cờ UTF-8), **không truyền API key** (`test_offline.py` kiểm: chương trình con `print(os.environ.get("DEEPSEEK_API_KEY"))` ra `None`); output cắt ở 2.000 ký tự kèm dòng `…[đã cắt, tổng N ký tự]` để LLM biết dữ liệu thiếu.
- **Script chỉ in kết quả cuối (gợi ý 2, tr. 33):** được dặn ở hai chỗ (system prompt, docstring của tool) và có trần cứng 2.000 ký tự phòng khi model lỡ in nhiều.
- **Đo input tokens qua `usage` (gợi ý 3):** `token_log.TokenLogger` là callback ghi `usage_metadata` mỗi lần gọi model (cả `cache_hit`), cộng thêm số lần chạy tool và số ký tự tool output quay về model.
- **Bộ dữ liệu:** `fixtures/make_logs.py` sinh 50 file `workspace/logs/service-XX.log` (11.411 dòng, 946.273 ký tự, seed 373). Đáp án đếm bằng cách parse lại chính các file, ghi ở `fixtures/ground_truth.json` (ngoài `workspace/` nên agent không đọc được qua `read_file`). Bẫy cố ý: nhiều dòng **WARN** nhắc đúng tên lỗi ("retrying after TimeoutError"), nên đếm thô tên lỗi sẽ ra số quá cao; câu hỏi chỉ tính dòng mức ERROR.
- **So sánh:** cùng một câu hỏi, cùng bộ log. Native: tools `list_files` + `read_file`. Code Mode: chỉ `run_python`. Chạy ở hai cỡ: 50 file và 10 file đầu (cỡ nhỏ để thấy tỉ lệ khi native chưa quá nặng).

## 4. Kết quả

### 4.1 B1: bảng token trước/sau compact

Chạy `python run_demo_b1.py` (file `demo-b1.txt`). `input_tokens` là số thật API trả về. Dòng ◄ là lần gọi model đầu tiên sau mỗi lần compact.

| # | Lượt | Loại | input_tokens | Ghi chú |
|---|---|---|---:|---|
| 2 | T1 | agent | 14.507 | sau `read_log` đầu tiên |
| 3 | T2 | agent | 14.991 | |
| 4 | T2 | checkpoint | 1.670 | **compact #1** (đo 21.401 token, ước lượng sau nén ≈ 1.112) |
| 5 | T2 | agent | **2.523** | ◄ sau compact #1 |
| 8 | T3 | agent | 10.739 | |
| 10 | T4 | agent | 23.289 | đỉnh của phiên có compact |
| 11 | T5 | checkpoint | 4.495 | **compact #2** (đo 24.360) |
| 12 | T5 | agent | **3.271** | ◄ sau compact #2: 23.289 → 3.271, giảm 86% |
| 16 | LÀM TIẾP | agent | 17.852 | |
| 17 | LÀM TIẾP | checkpoint | 5.378 | **compact #3** (đo 22.882) |
| 18 | LÀM TIẾP | agent | **4.210** | ◄ sau compact #3 |

Đối chứng chạy lại đúng kịch bản nhưng không compact:

| Chế độ | Số lần gọi model | Tổng input | Input đỉnh | Output | Cache hit |
|---|---:|---:|---:|---:|---:|
| Compact | 18 (3 lần là tạo checkpoint) | **168.844** | **23.289** | 10.389 | 97.152 |
| Baseline (không compact) | 15 | 544.591 | 64.725 | 8.148 | 454.144 |

Compact tốn **31%** tổng input tokens của baseline (đã tính 11.543 input tokens của 3 lần tạo checkpoint), đỉnh context 23.289 so với 64.725. Số liệu là của lần chạy cuối, sau khi sửa code theo review độc lập (mục 5).

**Checkpoint thật** (lần compact cuối, rút gọn; bản đầy đủ trong `demo-b1.txt`):

```
goal: Điều tra nguyên nhân lỗi API POST /checkout thỉnh thoảng trả HTTP 500 và đề xuất/áp dụng cách khắc phục.
current_state: Đã đọc đủ 3 log ..., xác nhận nguyên nhân 2 tầng ... Người dùng vừa chọn phương án (b): revert timeout + sửa
  order_service.create để nhả connection trước khi gọi gateway, rồi chạy lại test. Việc gọi apply_fix và run_tests CHƯA thực hiện. ...
constraints:
- KHÔNG đổi API công khai /checkout: path, request, response giữ nguyên
- KHÔNG restart production
findings:
- (×14) ERROR POST /checkout 500 DBPoolExhaustedError: connection pool exhausted (active=20/20, waiting=5..19) ...
- db-pool.log: (×12) ERROR QueuePool limit of size 20 overflow 0 reached, connection timed out, timeout=30 ...
- db-pool.log: (×51) WARN connection c-827 held by payment_client.charge for 10.0s (mức 8.0–12.9s ...)
- payment-gateway.log: (×37) WARN slow response ... (8–12s ...); (×5) ERROR upstream timeout after 12000ms ...
- Kết luận: tầng kích hoạt là payment gateway chậm 8–12s ...; tầng khuếch đại là order_service.py:41 giữ DB connection
  xuyên suốt lời gọi gateway → cạn pool 20 connection ...
failed_attempts:
- Tăng timeout lấy connection từ DB pool lên 30 giây qua apply_fix ... rồi run_tests → vẫn 3 failed, 200 passed, cùng thông báo lỗi ...
next_action: Gọi apply_fix theo phương án (b): (1) revert DB pool timeout về giá trị gốc, (2) sửa app/services/order_service.py để
  nhả DB connection trước khi gọi payment_client.charge ...; sau đó chạy run_tests() và báo cáo kết quả ...
```

Cả 3 checkpoint của lần chạy cuối đều có `constraints` đúng hai ràng buộc thật của user (sau khi siết prompt; trước đó `constraints` từng lẫn việc trợ lý đã làm). Compact #1 cảnh báo `checkpoint thiếu trường ['failed_attempts']`: đúng sự thật vì lúc đó chưa thử cách nào (validate bắt trường rỗng hoạt động).

**Tự kiểm PASS/FAIL** (code chấm bằng keyword trên câu trả lời, không dựa vào lời agent tự khai):

| Kiểm tra | Compact | Baseline |
|---|---|---|
| Compact kích hoạt ≥ 1 lần | PASS (3 lần) | không áp dụng |
| Nhớ lỗi đang điều tra (`/checkout`, 500/pool) | PASS | PASS |
| Nhớ cách đã thử + kết quả (tăng timeout, không hiệu quả) | PASS | PASS |
| Nhớ ràng buộc (không đổi API công khai) | PASS | PASS |
| Bước tiếp theo hợp lý (giải phóng/nhả kết nối DB, không chỉ nhắc payment gateway) | PASS | PASS |
| Agent làm tiếp đúng task (áp fix đúng rồi chạy lại test) | PASS | PASS |
| **KẾT QUẢ B1** | **PASS** | |

Lưu ý khi đọc: baseline cũng trả lời đúng vì toàn bộ lịch sử còn nguyên trong context. Lợi ích của compact ở đây là **kích thước context** (đỉnh thấp hơn 2,8 lần, tổng input chỉ 31%), không phải độ đúng; nó có giá trị khi lịch sử dài hơn context window hoặc khi cần kìm chi phí.

### 4.2 B2: native so với Code Mode

Chạy `python run_demo_b2.py` (file `demo-b2.txt`). Câu hỏi: lỗi ERROR nào nhiều nhất trên các file log, tổng bao nhiêu, file nào chứa nhiều nhất. Đáp án đúng 50 file: `TimeoutError` 174 lần, `service-37.log` 16 lần (ground truth tự kiểm, cả 4 ý).

| Chế độ | File | Lần gọi model | Lần chạy tool | **Tổng input_tokens** | Input đỉnh | Tool output → context | Đúng? |
|---|---:|---:|---:|---:|---:|---:|---|
| Native | 50 | 8 | 51 | **1.622.134** | 412.843 | 968.136 ký tự | ĐÚNG |
| **Code Mode** | 50 | 4 | 3 | **6.564** | 2.251 | 1.495 ký tự | ĐÚNG |
| Native | 10 | 4 | 11 | 132.603 | 84.968 | 199.157 ký tự | ĐÚNG |
| **Code Mode** | 10 | 3 | 2 | 4.327 | 2.013 | 1.665 ký tự | ĐÚNG |

Native tốn gấp **247 lần** (50 file) và **30,6 lần** (10 file) input tokens của Code Mode. Cache hit (từ `traces/*.jsonl`): native 50 file 1.216.384 / 1.622.134, Code Mode 5.504 / 6.564.

Hai điều đáng ghi:

1. Native **không tràn context** và không chạm giới hạn gọi model: model này nhận được context rất lớn (đỉnh 412.843 token), và gọi nhiều `read_file` song song trong một message (51 tool call chỉ trong 8 lần gọi model). Nhưng mỗi lần gọi model đều gửi lại toàn bộ log đã đọc, nên tổng input phình theo kiểu cộng dồn: 849 → 3.428 → 84.110 → 166.294 → 249.416 → 332.150 → 373.044 → 412.843 (`traces/b2-native-50files.jsonl`).
2. Code Mode: chương trình model viết đọc 50 file trong runtime, lọc đúng dòng ERROR bằng regex (không dính bẫy WARN), chỉ in vài dòng kết quả; raw log không vào context (1.495 ký tự quay về so với 968.136 ký tự của native).

## 5. Giới hạn

- **Không phải sandbox.** `run_python` có timeout, cwd và env tối thiểu nhưng chương trình vẫn đọc/ghi được ngoài `workspace/` với quyền của user (tr. 31: chạy trong runtime riêng chưa phải sandbox). Production cần sandbox thật, permission check, resource limit. Chỉ dùng với dữ liệu giả.
- **Model sinh ngẫu nhiên.** Mỗi lần chạy số lần gọi tool, nội dung checkpoint, token hơi khác. Số trong báo cáo là một lần chạy (`temperature=0` nhưng thinking mode vẫn có biến thiên); ba lần chạy B1 trong lúc làm bài đều cho tỉ lệ compact/baseline xấp xỉ 31% (31,1%, 30,7%, 31,0%).
- **Ngưỡng compact nhỏ để demo** (20.000 token), thực tế nên 60-70% context window.
- **Keyword check là kiểm tra thô.** Nó bỏ sót cách diễn đạt khác. Lần chạy đầu bước "làm tiếp" bị chấm FAIL dù agent mô tả đúng fix ("thu hẹp khối `with`... trả connection về pool"), vì từ điển chưa có "trả về pool"; đã bổ sung từ điển và chạy lại toàn bộ. Review code độc lập còn chỉ ra bộ chấm ban đầu quá dễ (bỏ dấu làm "vẫn/vấn" thành "van"), nên đã siết: cụm phủ định phải nằm gần chữ "timeout", bước tiếp phải có động từ giải phóng/nhả kết nối, và "làm tiếp" phải có fix đúng được áp ngay trong lượt đó; `test_offline.py` kiểm bộ chấm cho qua câu đúng và loại câu sai. Fix sai/đúng của `apply_fix` cũng nhận bằng từ khoá, không phải test code thật. Dữ liệu log/test là giả.
- **`run_python` vẫn đọc được ngoài workspace.** Tiến trình con không có API key trong env, nhưng không phải sandbox nên chương trình vẫn có thể mở `../.env` hay `../fixtures/ground_truth.json` nếu nó muốn; để đáp án ngoài `workspace/` chỉ chặn được `read_file`. Env của tiến trình con cũng không có `TEMP`/`TMP` (chưa cần cho bài này).
- **Số "sau compact" trong dòng `=== COMPACTED ===` là ước lượng** (ký tự/4, chưa tính system prompt và tool schema); số thật là `input_tokens` của lần gọi model kế tiếp trong bảng.
- **Compact phá prefix cache.** Sau mỗi lần compact, `cache_hit` rơi về 896 token (chỉ còn system prompt + tool schema): 58% input của phiên compact là cache hit so với 83% của baseline (97.152/168.844 và 454.144/544.591). Tiết kiệm token chưa chắc tiết kiệm tiền tương ứng khi token cache hit rẻ hơn (Slide Buổi 7, tr. 35-46, prompt caching); mình chưa đo chi phí tiền.
- **Checkpoint phình dần khi nén tăng dần** (tr. 21: incremental summary có rủi ro lỗi tích lũy): input của lần tạo checkpoint tăng 1.670 → 4.495 → 5.378 token vì checkpoint cũ được gộp vào. Chưa có cơ chế giới hạn kích thước checkpoint. Việc LLM tự phân loại "ràng buộc" cũng có rủi ro: ở các lần chạy đầu `constraints` từng lẫn việc trợ lý đã làm và yêu cầu một lần; sau khi siết prompt thì cả 3 checkpoint của lần chạy cuối sạch, nhưng vẫn chưa có kiểm tự động rằng ràng buộc thật còn sau khi nén (chỉ kiểm gián tiếp qua câu hỏi lại).
- **Lượt user của B1 là kịch bản cố định**, phiên chỉ ~7 lượt; chưa thử phiên dài hàng trăm lượt.

## 6. Hai kỹ thuật bổ sung nhau (Slide 34)

| | Code Mode (B2) | Compaction (B1) |
|---|---|---|
| Thời điểm | Khi chạy tools: đọc 50 file trong runtime | Sau khi dữ liệu đã tích lũy trong context |
| Tác dụng đo được | Chặn rác vào: 968.136 ký tự raw log → 1.495 ký tự | Dọn rác đã vào: đỉnh 64.725 → 23.289 token, 23.289 → 3.271 sau một lần nén |
| Rủi ro | Code lỗi, quyền truy cập (không phải sandbox) | Mất state/ràng buộc (giảm bằng structured checkpoint + `constraints`), usage cũ, ToolMessage mồ côi |

Kết hợp (slide 34): Code Mode giảm tốc độ context phình ra, compaction làm checkpoint cho session dài. Trong bài này hai demo chạy riêng; chưa ghép Code Mode vào cùng một session với compaction.

## 7. Cách chạy lại

```bash
pip install -r requirements.txt          # copy .env.example thành .env, điền DEEPSEEK_API_KEY
python test_offline.py                   # không cần API
python run_demo_b1.py                    # ghi demo-b1.txt, traces/b1-*.jsonl
python run_demo_b2.py                    # ghi demo-b2.txt, traces/b2-*.jsonl
```

Zip nộp bài không chứa `.env`, `.venv`, `__pycache__`, `traces/archive/` (bản raw của log đã rút gọn); `scripts/package_source.py` kiểm lại zip không có file `.env` và không có giá trị API key.

## 8. Câu hỏi còn mở

- Ngưỡng compact nên đặt theo tỉ lệ context window của model thực tế (chưa biết giới hạn chính xác của `deepseek-flash`); bài này giữ 20.000 token để demo.
- Chưa so chi phí bằng tiền có tính cache hit giữa compact và baseline.
