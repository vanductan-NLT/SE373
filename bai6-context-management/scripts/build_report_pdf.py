"""Dựng BAO_CAO.pdf (báo cáo nộp) từ output THẬT của các lần chạy, không gõ tay số liệu.

    python scripts/build_report_pdf.py

Nguồn: demo-b1.txt, demo-b2.txt, traces/*.jsonl (do run_demo_b1.py / run_demo_b2.py ghi) và hai lệnh chạy ngay lúc dựng
(python test_offline.py, python scripts/show_prune_example.py; cả hai không cần API). Mỗi "ảnh chụp" là khối terminal
dựng từ đúng các dòng output đó (đoạn nào lược bớt thì có dòng "[… lược bớt …]"). Ra output/BAO_CAO.html rồi in PDF bằng
Edge/Chrome headless.
"""

from __future__ import annotations

import html
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_HTML = ROOT / "output" / "BAO_CAO.html"
OUT_PDF = ROOT / "BAO_CAO.pdf"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
OMIT = "[… lược bớt …]"


# ---------- đọc nguồn ----------

def read_lines(name: str) -> list[str]:
    return (ROOT / name).read_text(encoding="utf-8").splitlines()


def find(lines: list[str], pattern: str, start: int = 0) -> int:
    for i in range(start, len(lines)):
        if re.search(pattern, lines[i]):
            return i
    raise ValueError(f"không thấy dòng khớp {pattern!r} từ dòng {start}")


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def run_live(*args: str) -> list[str]:
    """Chạy một lệnh Python trong project, lấy stdout (đúng thứ người chấm sẽ thấy khi tự chạy)."""
    done = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True)
    return done.stdout.rstrip().splitlines()


def num(text: str) -> int:
    return int(text.replace(",", ""))


# ---------- khối terminal ----------

def colorize(escaped: str) -> str:
    escaped = re.sub(r"\bPASS\b", '<span class="ok">PASS</span>', escaped)
    escaped = re.sub(r"\bFAIL\b", '<span class="bad">FAIL</span>', escaped)
    escaped = re.sub(r"^(=== (?:COMPACTED|PRUNED).*)$", r'<span class="hl">\1</span>', escaped, flags=re.M)
    escaped = re.sub(r"^(=== hết checkpoint ===)$", r'<span class="hl">\1</span>', escaped, flags=re.M)
    escaped = re.sub(r"^(CẢNH BÁO.*)$", r'<span class="warn">\1</span>', escaped, flags=re.M)
    escaped = re.sub(r"^(\s*\[… lược bớt.*)$", r'<span class="dim">\1</span>', escaped, flags=re.M)
    return escaped


def terminal(title: str, lines: list[str], caption: str = "") -> str:
    body = colorize(html.escape("\n".join(lines)))
    cap = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure><div class="term"><div class="bar">{html.escape(title)}</div><pre>{body}</pre></div>{cap}</figure>'


# ---------- biểu đồ SVG ----------

def line_chart(compact: list[dict], baseline: list[dict], threshold: int) -> str:
    w, h, left, right, top, bottom = 720, 250, 54, 14, 16, 30
    xmax, ymax = max(len(compact), len(baseline)), 70_000
    sx = lambda n: left + (n - 1) / (xmax - 1) * (w - left - right)  # noqa: E731
    sy = lambda v: top + (1 - v / ymax) * (h - top - bottom)  # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%">']
    for v in range(0, ymax + 1, 10_000):
        out.append(f'<line x1="{left}" y1="{sy(v):.1f}" x2="{w - right}" y2="{sy(v):.1f}" stroke="#e5e7eb"/>'
                   f'<text x="{left - 6}" y="{sy(v) + 3:.1f}" font-size="9" text-anchor="end" fill="#6b7280">{v // 1000}k</text>')
    out.append(f'<line x1="{left}" y1="{sy(threshold):.1f}" x2="{w - right}" y2="{sy(threshold):.1f}" stroke="#dc2626" stroke-dasharray="5 4"/>'
               f'<text x="{w - right}" y="{sy(threshold) - 4:.1f}" font-size="9" text-anchor="end" fill="#dc2626">ngưỡng compact {threshold:,}</text>')
    for n in range(1, xmax + 1):
        out.append(f'<text x="{sx(n):.1f}" y="{h - 14}" font-size="9" text-anchor="middle" fill="#6b7280">{n}</text>')
    out.append(f'<text x="{(left + w - right) / 2:.0f}" y="{h - 2}" font-size="9" text-anchor="middle" fill="#374151">lần gọi model thứ n (mỗi điểm = một số `usage` thật)</text>')

    def series(rows: list[dict], color: str, label: str, label_dy: int) -> None:
        agent = [r for r in rows if r["kind"] == "agent"]
        out.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="' + " ".join(f"{sx(r['n']):.1f},{sy(r['input_tokens']):.1f}" for r in agent) + '"/>')
        out.extend(f'<circle cx="{sx(r["n"]):.1f}" cy="{sy(r["input_tokens"]):.1f}" r="3" fill="{color}"/>' for r in agent)
        peak = max(agent, key=lambda r: r["input_tokens"])
        px = sx(peak["n"])
        anchor, dx = ("end", -8) if px > w - 150 else ("start", 6)  # nhãn sát mép phải thì viết ngược vào trong
        out.append(f'<text x="{px + dx:.1f}" y="{sy(peak["input_tokens"]) + label_dy:.1f}" text-anchor="{anchor}" font-size="10" font-weight="700" fill="{color}">{label} đỉnh {peak["input_tokens"]:,}</text>')

    series(baseline, "#6b7280", "Không compact", -2)
    series(compact, "#2563eb", "Có compact", -6)
    for i, r in enumerate((r for r in compact if r["kind"] == "checkpoint"), 1):  # lần gọi LLM tạo checkpoint
        cx, cy = sx(r["n"]), sy(r["input_tokens"])
        out.append(f'<polygon points="{cx:.1f},{cy - 6:.1f} {cx + 5:.1f},{cy:.1f} {cx:.1f},{cy + 6:.1f} {cx - 5:.1f},{cy:.1f}" fill="#f59e0b"/>'
                   f'<text x="{cx:.1f}" y="{cy - 10:.1f}" text-anchor="middle" font-size="8.5" fill="#b45309" style="paint-order:stroke;stroke:#fff;stroke-width:3px">checkpoint #{i}</text>')
    out.append("</svg>")
    return f'<div class="chart">{"".join(out)}</div>'


def hbars(title: str, rows: list[tuple[str, int, str]], unit: str) -> str:
    """Thanh ngang thang log (giá trị lệch nhau hàng trăm lần), ghi rõ giá trị thật ở cuối thanh."""
    w, bar_h, left = 270, 18, 118
    vmax = max(v for _, v, _ in rows)
    out = [f'<svg viewBox="0 0 {left + w + 120} {len(rows) * (bar_h + 6) + 26}" width="100%"><text x="0" y="11" font-size="10" font-weight="700">{html.escape(title)}</text>']
    for i, (label, value, color) in enumerate(rows):
        y = 20 + i * (bar_h + 6)
        width = max(3, math.log10(value + 1) / math.log10(vmax + 1) * w)
        out.append(f'<text x="{left - 6}" y="{y + 13}" font-size="9.5" text-anchor="end">{html.escape(label)}</text>'
                   f'<rect x="{left}" y="{y}" width="{width:.0f}" height="{bar_h}" fill="{color}" rx="2"/>'
                   f'<text x="{left + width + 5:.0f}" y="{y + 13}" font-size="9.5" font-weight="700">{value:,} {unit}</text>')
    out.append("</svg>")
    return f'<div class="chart">{"".join(out)}</div>'


# ---------- trích đoạn B1 ----------

def b1_session_excerpt(lines: list[str]) -> list[str]:
    """Từ đầu phiên tới banner compact đầu tiên: lời user, tool call, kích thước tool result, ngữ cảnh."""
    end = find(lines, r"^\[CHECKPOINT\]")
    keep = re.compile(r"^(T\d USER|  \[tool call\]|  \[tool result\]|  \[ctx\]|=== COMPACTED|messages |CẢNH BÁO)")
    out, start = [], find(lines, r"^T1 USER")
    for line in lines[start:end]:
        if keep.match(line):
            out.append(line)
        elif line.startswith("AGENT:"):
            out.append("AGENT: [… lược bớt câu trả lời của agent …]")
    return out


def b1_block(lines: list[str], start_pat: str, end_pat: str, occurrence: int = 1) -> list[str]:
    i = -1
    for _ in range(occurrence):
        i = find(lines, start_pat, i + 1)
    return lines[i:find(lines, end_pat, i) + 1]


def b1_table(lines: list[str], header: str) -> list[str]:
    i = find(lines, header)
    j = i + 2
    while j < len(lines) and lines[j].strip() and not lines[j].startswith("="):
        j += 1
    return lines[i:j]


def b1_answer_and_checks(lines: list[str]) -> list[str]:
    start = find(lines, r"^\[COMPACT\] câu trả lời sau compact")
    first_check = find(lines, r"^  lỗi đang điều tra", start)
    info = find(lines, r"\(thông tin thêm\)", first_check)
    out = lines[start:first_check]
    for line in lines[first_check:info]:
        out.append(re.sub(r" \| fix đã áp: .*$", " | fix đã áp: […]", line))
    out.append(lines[find(lines, r"^KẾT QUẢ B1")])
    return out


# ---------- trích đoạn B2 ----------

def b2_run_block(lines: list[str], header: str) -> list[str]:
    i = find(lines, header) + 2
    j = find(lines, r"^=+$", i) if any(re.match(r"^=+$", x) for x in lines[i:]) else len(lines)
    block = lines[i:j]
    while block and not block[-1].strip():
        block.pop()
    return block


def b2_native_short(block: list[str]) -> list[str]:
    cut = next(i for i, line in enumerate(block) if line.startswith("### Phân bố"))
    answer_end = next(i for i, line in enumerate(block) if line.startswith("Đáp án đúng"))
    return block[1:cut] + [OMIT] + block[answer_end:]  # bỏ dòng USER (trùng câu hỏi ở khối Code Mode)


# ---------- ghép báo cáo ----------

def build_html() -> str:
    b1, b2 = read_lines("demo-b1.txt"), read_lines("demo-b2.txt")
    trace_c, trace_b = read_jsonl("traces/b1-compact.jsonl"), read_jsonl("traces/b1-baseline.jsonl")

    row = lambda name: re.match(rf"^{name}\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", b1[find(b1, rf'^{name}\s+\d+')])  # noqa: E731
    mc, mb = row("COMPACT"), row(r"BASELINE \(không compact\)")
    pct = re.search(r"Compact tốn (\d+)%", "\n".join(b1)).group(1)
    b2rows = {}
    for line in b2:
        m = re.match(r"^(native|code)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+) ký tự\s+(ĐÚNG|SAI)", line)
        if m:
            b2rows[(m[1], int(m[2]))] = {"input": num(m[5]), "peak": num(m[6]), "chars": num(m[7]), "calls": int(m[3]), "tools": int(m[4]), "ok": m[8] == "ĐÚNG"}
    ratio50 = b2rows[("native", 50)]["input"] / b2rows[("code", 50)]["input"]
    assert "KẾT QUẢ B1 (chỉ tính lần chạy có compact): PASS" in b1 and any("KẾT QUẢ B2" in x and "PASS" in x for x in b2), "demo chưa PASS, không dựng báo cáo"

    offline = run_live("test_offline.py")
    prune = run_live("scripts/show_prune_example.py")
    compact_events = json.loads((ROOT / "traces/b1-compaction-events.json").read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "fixtures/ground_truth.json").read_text(encoding="utf-8"))
    css = (Path(__file__).with_name("report.css")).read_text(encoding="utf-8")
    first, second = compact_events[0], compact_events[1]
    ckpt_idx = [i for i, r in enumerate(trace_c) if r["kind"] == "checkpoint"][1]  # lần compact thứ hai (khớp Hình 2)
    drop_before, drop_after = trace_c[ckpt_idx - 1]["input_tokens"], trace_c[ckpt_idx + 1]["input_tokens"]
    raw_chars, pruned_chars = re.search(r"thô \d+ dòng / ([\d,]+) ký tự → rút gọn \d+ dòng / ([\d,]+)", prune[0]).groups()

    parts = [f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>BTVN#6 Challenge B</title><style>{css}</style></head><body>']
    parts.append(f"""
<h1>BTVN#6 · Challenge B: Context management</h1>
<table>
<tr><th></th><th>B1 Compact (bắt buộc)</th><th>B2 Code Mode (điểm cộng)</th></tr>
<tr><td><b>Kết quả</b></td><td><span class="pass">PASS</span> nén {len(compact_events)} lần, agent vẫn nhớ lỗi / cách đã thử / ràng buộc / bước tiếp</td><td><span class="pass">PASS</span> trả lời đúng ground truth ở cả 50 và 10 file</td></tr>
<tr><td><b>Số đo chính</b></td><td>Tổng input tokens <b>{num(mc[2]):,}</b> (compact) so với <b>{num(mb[2]):,}</b> (không compact) = {pct}%. Đỉnh context {num(mc[3]):,} so với {num(mb[3]):,}</td><td>50 file: Code Mode <b>{b2rows[("code", 50)]["input"]:,}</b> input tokens, native <b>{b2rows[("native", 50)]["input"]:,}</b> (gấp {ratio50:.0f} lần). Raw log vào context: {b2rows[("code", 50)]["chars"]:,} so với {b2rows[("native", 50)]["chars"]:,} ký tự</td></tr>
<tr><td><b>Cách làm</b></td><td><code>CompactionMiddleware</code> chạy trước mỗi lần gọi model: rút gọn tool output dài, nhờ LLM viết checkpoint 7 trường, thay lịch sử cũ bằng checkpoint + vài message gần nhất</td><td>Tool <code>run_python</code>: model viết chương trình, harness chạy trong tiến trình riêng, model chỉ nhận phần chương trình <code>print</code>; so với native đọc từng file bằng <code>read_file</code></td></tr>
</table>
""")

    parts.append("<h2>1. B1 Compact: session dài, nén có cấu trúc, agent vẫn làm đúng việc</h2>")
    parts.append(f"""<table>
<tr><th>Bước pipeline (slide tr. 26)</th><th>Cài đặt (<code>compaction.py</code>, <code>pruning.py</code>)</th><th>Slide</th></tr>
<tr><td>Observe token budget</td><td>usage thật của AIMessage gần nhất + ước lượng phần mới; ngưỡng {20_000:,} token (cố ý nhỏ để demo)</td><td>tr. 25</td></tr>
<tr><td>Prune tool output</td><td>giữ dòng ERROR/FAIL (gộp trùng, đếm số lần), gộp dòng lặp, raw lưu <code>traces/archive/</code></td><td>tr. 19, 23</td></tr>
<tr><td>Build checkpoint</td><td>LLM + structured output, 7 trường <code>goal … next_action</code>; trường rỗng thì cảnh báo</td><td>tr. 22</td></tr>
<tr><td>Reinject / Resume</td><td>system prompt do <code>create_agent</code> gắn lại mỗi lần gọi; ràng buộc user nằm trong <code>constraints</code>; hỏi lại + cho làm tiếp để kiểm</td><td>tr. 22, 26</td></tr>
<tr><td>Chọn điểm cắt</td><td>giữ nguyên 4 message cuối, lùi điểm cắt về chỗ không làm ToolMessage mồ côi (nếu không API báo lỗi 400); yêu cầu hiện tại của user được ghi nguyên văn vào checkpoint</td><td>tr. 23</td></tr>
<tr><td>Cách kiểm</td><td>kịch bản debug giả (3 log ~340-380 dòng + 366 dòng test, sinh cố định): 5 lượt user, rồi hỏi lại và cho làm tiếp; chạy thêm một lần không compact để đối chứng</td><td>tr. 32-33</td></tr>
</table>""")
    parts.append(terminal("$ python run_demo_b1.py   (trích demo-b1.txt: phiên dài, tool output lớn, compact kích hoạt)", b1_session_excerpt(b1),
                          f"<b>Hình 1.</b> Tool output lớn (xem cột ký tự); vượt ngưỡng thì compact chạy lần đầu: {first['tokens_before']:,} token, {first['messages_before']} → {first['messages_after']} messages."))
    parts.append("<figure>" + line_chart(trace_c, trace_b, 20_000)
                 + "<figcaption><b>Hình 2.</b> Input tokens của từng lần gọi model. Không compact (xám): tăng dần theo từng tool output. Có compact (xanh): mỗi lần vượt ngưỡng lại rơi về vài nghìn (hình thoi cam = lần gọi LLM tạo checkpoint).</figcaption></figure>")
    parts.append(terminal("$ python run_demo_b1.py   (trích demo-b1.txt: compact lần 2 và checkpoint thật)", b1_block(b1, r"^=== COMPACTED", r"^=== hết checkpoint", occurrence=2),
                          f"<b>Hình 3.</b> Structured checkpoint đủ 7 trường (slide tr. 22), {second['messages_before']} → {second['messages_after']} messages. Hai ràng buộc user nói ở lượt đầu vẫn nằm trong <code>constraints</code>."))
    parts.append(terminal("$ python run_demo_b1.py   (trích demo-b1.txt: bảng token, số `usage` thật)", b1_table(b1, r"^BẢNG TOKEN · COMPACT"),
                          f"<b>Hình 4.</b> Dòng ◄ là lần gọi model đầu tiên sau mỗi lần compact. Lần 2: {drop_before:,} → {drop_after:,} token (giảm {1 - drop_after / drop_before:.0%})."))
    parts.append(terminal("$ python run_demo_b1.py   (trích demo-b1.txt: tổng token hai chế độ)", b1_block(b1, r"^chế độ ", r"^Compact tốn"),
                          "<b>Hình 5.</b> Cùng kịch bản, cùng lượt user. Số lần gọi của compact nhiều hơn vì có 3 lần tạo checkpoint, đã tính cả vào tổng."))
    parts.append(terminal("$ python run_demo_b1.py   (trích demo-b1.txt: hỏi lại sau compact + tự kiểm)", b1_answer_and_checks(b1),
                          "<b>Hình 6.</b> Sau compact, agent trả lời đúng cả 4 ý và làm tiếp đúng việc (áp fix đúng rồi chạy lại test). Code chấm bằng keyword, không dựa vào lời agent tự khai."))
    parts.append("<h3>Rút gọn tool output và bẫy ToolMessage mồ côi (chạy trực tiếp, không cần API)</h3>")
    parts.append(terminal("$ python scripts/show_prune_example.py", prune[:14] + [OMIT],
                          f"<b>Hình 7.</b> Slide tr. 23: giữ lỗi chưa giải quyết, rút gọn output dài, bỏ log trùng (gộp thành ×N). {raw_chars} ký tự còn {pruned_chars}."))
    parts.append(terminal("$ python test_offline.py", offline,
                          "<b>Hình 8.</b> Bẫy chính của compact: đuôi giữ lại không được bắt đầu bằng ToolMessage mồ côi (API báo 400). Test thử mọi điểm cắt, cả trường hợp gọi tool song song."))

    native50 = b2_run_block(b2, r"^B2 · NATIVE · 50 file")
    code50 = b2_run_block(b2, r"^B2 · CODE · 50 file")
    parts.append("<h2>2. B2 Code Mode: 50 file log, raw log không vào context</h2>")
    parts.append(f"""<ul class="small">
<li><b>Code chạy ở đâu:</b> LLM chỉ viết chương trình (tool call <code>run_python</code>); <b>harness</b> chạy nó trong tiến trình Python riêng, LLM chỉ nhận phần chương trình <code>print</code> (slide tr. 28).</li>
<li><b>Giới hạn:</b> cwd = <code>workspace/</code>, timeout 15 giây, env không có API key, output cắt ở 2,000 ký tự. <b>Không phải sandbox bảo mật</b> (slide tr. 31).</li>
<li><b>So sánh:</b> cùng một câu hỏi, cùng bộ log, hai chế độ. Native dùng <code>list_files</code> + <code>read_file</code>; Code Mode chỉ dùng <code>run_python</code> (chương trình chỉ in kết quả cuối). Đo tổng <code>input_tokens</code> bằng <code>usage</code>, chấm đúng/sai với ground truth, chạy ở 50 file và 10 file.</li>
<li><b>Bộ dữ liệu:</b> 50 file, {truth["total_lines"]:,} dòng, đáp án đếm bằng cách parse lại chính các file (ground truth ngoài <code>workspace/</code>); bẫy: nhiều dòng WARN nhắc đúng tên lỗi, chỉ tính dòng ERROR.</li>
</ul>""")
    parts.append('<div class="cols">' + hbars("Tổng input_tokens (thang log)", [
        ("Native · 50 file", b2rows[("native", 50)]["input"], "#6b7280"), ("Code Mode · 50 file", b2rows[("code", 50)]["input"], "#2563eb"),
        ("Native · 10 file", b2rows[("native", 10)]["input"], "#9ca3af"), ("Code Mode · 10 file", b2rows[("code", 10)]["input"], "#60a5fa")], "")
        + hbars("Tool output quay về context (thang log)", [
        ("Native · 50 file", b2rows[("native", 50)]["chars"], "#6b7280"), ("Code Mode · 50 file", b2rows[("code", 50)]["chars"], "#2563eb"),
        ("Native · 10 file", b2rows[("native", 10)]["chars"], "#9ca3af"), ("Code Mode · 10 file", b2rows[("code", 10)]["chars"], "#60a5fa")], "ký tự") + "</div>")
    parts.append(f'<p class="small"><b>Hình 9.</b> Cùng câu hỏi, cùng bộ log, thang log vì chênh nhau hàng trăm lần (50 file: native gấp {ratio50:.0f} lần).</p>')
    parts.append(terminal("$ python run_demo_b2.py   (trích demo-b2.txt: bảng so sánh)", b1_block(b2, r"^SO SÁNH \(cùng", r"^KẾT QUẢ B2"),
                          f"<b>Hình 10.</b> Cả hai chế độ đều đúng; khác biệt nằm ở token. Native không tràn context vì model này có context rất lớn (đỉnh {b2rows[('native', 50)]['peak']:,} token)."))
    parts.append(terminal("$ python run_demo_b2.py   (trích demo-b2.txt: Code Mode, 50 file)", code50,
                          f"<b>Hình 11.</b> Model tự viết chương trình đọc 50 file, lọc đúng dòng ERROR bằng regex, chỉ in vài dòng; {b2rows[('code', 50)]['calls']} lần gọi model, {b2rows[('code', 50)]['tools']} lần chạy tool."))
    parts.append(terminal("$ python run_demo_b2.py   (trích demo-b2.txt: native, 50 file)", b2_native_short(native50),
                          f"<b>Hình 12.</b> Native: {b2rows[('native', 50)]['calls']} lần gọi model, {b2rows[('native', 50)]['tools']} lần chạy tool; mỗi lần gọi gửi lại toàn bộ log đã đọc nên tổng input phình lên."))
    parts.append("</body></html>")
    return "".join(parts)


def print_pdf() -> None:
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if browser is None:
        raise SystemExit("Không thấy Edge/Chrome để in PDF")
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={OUT_PDF}", OUT_HTML.as_uri()],
                   check=True, capture_output=True, timeout=120)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print_pdf()
    print(f"{OUT_PDF} ({OUT_PDF.stat().st_size / 1024:.0f} KB)")
