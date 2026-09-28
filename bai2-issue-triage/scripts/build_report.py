"""Build the PDF after screenshots and a public Drive URL exist."""

import argparse
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf/BTVN2_Issue_Triage_Van_Duc_Tan_24521586.pdf"
SCREENSHOTS = ROOT / "docs/screenshots"


def find_font() -> Path:
    for path in [Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/calibri.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]:
        if path.exists():
            return path
    raise RuntimeError("Không tìm thấy font Unicode.")


def page_number(canvas, doc) -> None:
    canvas.saveState(); canvas.setFont("Vietnamese", 9); canvas.setFillColor(colors.HexColor("#5B6F68"))
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"Trang {doc.page}"); canvas.restoreState()


def image(path: Path, width: float = 170 * mm) -> Image:
    if not path.exists():
        raise FileNotFoundError(f"Thiếu screenshot: {path}")
    item = Image(str(path)); ratio = width / item.imageWidth
    item.drawWidth = width; item.drawHeight = item.imageHeight * ratio
    return item


def build_pdf(drive_url: str) -> Path:
    if not drive_url.startswith("https://"):
        raise ValueError("Drive URL phải là link HTTPS public.")
    shots = [SCREENSHOTS / name for name in ["streamlit_result.png", "cli_structured.png", "cli_trace.png"]]
    for shot in shots:
        if not shot.exists(): raise FileNotFoundError(f"Thiếu screenshot: {shot}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("Vietnamese", str(find_font())))
    styles = getSampleStyleSheet()
    base = ParagraphStyle("BaseVi", parent=styles["BodyText"], fontName="Vietnamese", fontSize=10.5, leading=16, textColor=colors.HexColor("#18312A"))
    title = ParagraphStyle("TitleVi", parent=base, fontSize=26, leading=32, alignment=TA_CENTER, textColor=colors.HexColor("#067647"), spaceAfter=14)
    heading = ParagraphStyle("HeadingVi", parent=base, fontSize=17, leading=22, textColor=colors.HexColor("#067647"), spaceBefore=10, spaceAfter=9)
    center = ParagraphStyle("CenterVi", parent=base, alignment=TA_CENTER)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm, title="BTVN#2 - Issue Triage mini-app", author="Văn Đức Tân")
    table = Table([["Bước", "Kết quả"], ["Structured output", "IssueTriage được Pydantic validate"], ["Tool call", "get_component_owner(component)"], ["Application", "Kiểm tra allowlist và thực thi lookup"], ["Final response", "Kết luận từ triage và tool result"]], colWidths=[45*mm, 115*mm])
    table.setStyle(TableStyle([("FONTNAME", (0,0), (-1,-1), "Vietnamese"), ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#DDF3E7")), ("GRID", (0,0), (-1,-1), .5, colors.HexColor("#BFD4C9")), ("VALIGN", (0,0), (-1,-1), "TOP"), ("PADDING", (0,0), (-1,-1), 7)]))
    story = [Spacer(1,35*mm), Paragraph("BTVN#2", title), Paragraph("ISSUE TRIAGE MINI-APP", title), Spacer(1,12*mm), Paragraph("Văn Đức Tân - 24521586 - SE373.R11", center), Spacer(1,22*mm), Paragraph("Source code Google Drive", heading), Paragraph(f'<link href="{drive_url}" color="#067647">{drive_url}</link>', center), PageBreak(), Paragraph("1. Mục tiêu và kiến trúc", heading), Paragraph("Ứng dụng nhận mô tả issue, tách instruction khỏi input, yêu cầu DeepSeek trả JSON, validate bằng Pydantic, sau đó cho phép model đề xuất tool. Application kiểm tra và thực thi tool; model không tự chạy code.", base), Spacer(1,5*mm), table, Paragraph("2. Kết quả Streamlit", heading), image(shots[0]), PageBreak(), Paragraph("3. Structured output trên CLI", heading), image(shots[1]), Spacer(1,5*mm), Paragraph("Output được parse JSON rồi validate schema và business invariants; severity không được suy ra bằng substring hoặc regex.", base), PageBreak(), Paragraph("4. Function-calling trace", heading), image(shots[2]), Spacer(1,5*mm), Paragraph("Trace chứng minh application kiểm tra arguments, thực thi hàm, gửi tool result về model rồi mới nhận final response.", base), Paragraph("5. Ước tính chi phí", heading), Paragraph("Chi phí dùng token usage thực tế của input mẫu. Công thức và giá giả định nằm trong docs/uoc_tinh_chi_phi.html; kịch bản tính 10.000 issue/tháng và toàn bộ input cache miss.", base)]
    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    if len(PdfReader(str(OUTPUT)).pages) < 4: raise RuntimeError("PDF thiếu trang dự kiến.")
    return OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--drive-url", required=True)
    print(build_pdf(parser.parse_args().drive_url))


if __name__ == "__main__": main()
