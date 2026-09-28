# Checklist tạo báo cáo PDF

1. Điền `.env`, chạy `python cli.py --write-cost-report`.
2. Chụp `docs/screenshots/streamlit_result.png`.
3. Chụp `docs/screenshots/cli_structured.png`.
4. Chụp `docs/screenshots/cli_trace.png`.
5. Chạy `python scripts/package_source.py`, upload ZIP lên Drive và bật
   `Anyone with the link - Viewer`.
6. Chạy `python scripts/build_report.py --drive-url "LINK_PUBLIC"`.
7. Render PDF bằng Poppler, kiểm tra mọi trang trước khi nộp.

Không đưa `.env`, API key hoặc ảnh có API key vào ZIP/PDF.
