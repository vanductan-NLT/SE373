"""Conservative DeepSeek cost estimate and HTML report."""

from datetime import date
from html import escape
from pathlib import Path

from .models import WorkflowResult

INPUT_PRICE_PER_MILLION = 0.14
OUTPUT_PRICE_PER_MILLION = 0.28
MONTHLY_ISSUES = 10_000


def estimate_cost(input_tokens: int, output_tokens: int, issues: int = MONTHLY_ISSUES) -> float:
    return issues * (
        input_tokens * INPUT_PRICE_PER_MILLION + output_tokens * OUTPUT_PRICE_PER_MILLION
    ) / 1_000_000


def build_cost_report(output_path: Path, sample_issue: str, result: WorkflowResult | None = None) -> None:
    input_tokens = result.total_input_tokens if result else 0
    output_tokens = result.total_output_tokens if result else 0
    monthly_cost = estimate_cost(input_tokens, output_tokens) if result else 0
    note = (
        "Token lấy trực tiếp từ usage của các DeepSeek API response trong lần chạy mẫu."
        if result
        else "Chưa có số đo live. Chạy python cli.py --write-cost-report sau khi cấu hình .env."
    )
    rows = (
        "".join(
            f"<tr><td>{escape(x.stage)}</td><td>{x.input_tokens:,}</td><td>{x.output_tokens:,}</td></tr>"
            for x in result.usage
        )
        if result
        else '<tr><td colspan="3">Đang chờ lần chạy DeepSeek thực tế</td></tr>'
    )
    html = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ước tính chi phí</title>
<style>:root{{--green:#067647;--ink:#18312a;--line:#d9e5df}}*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,sans-serif;color:var(--ink);background:#f4f8f6}}main{{max-width:900px;margin:40px auto;padding:36px;background:white;border-radius:18px;box-shadow:0 12px 32px #173a2920}}h1,h2{{color:var(--green)}}.issue,.formula{{padding:16px;background:#eef7f2;border-left:4px solid var(--green);border-radius:8px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:20px 0}}.card{{padding:18px;border:1px solid var(--line);border-radius:12px}}.value{{font-size:1.5rem;font-weight:700;color:var(--green)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;border-bottom:1px solid var(--line);text-align:left}}th{{background:#eef7f2}}a{{color:var(--green)}}@media(max-width:650px){{main{{margin:0}}.cards{{grid-template-columns:1fr}}}}</style></head>
<body><main><p>BTVN#2 · Văn Đức Tân · 24521586 · SE373.R11</p><h1>Ước tính chi phí Issue Triage</h1>
<p>Ngày: {date.today().isoformat()} · Model: deepseek-flash</p><h2>Input mẫu</h2><p class="issue">{escape(sample_issue)}</p><p>{note}</p>
<table><thead><tr><th>Model call</th><th>Input token</th><th>Output token</th></tr></thead><tbody>{rows}</tbody></table>
<div class="cards"><div class="card">Tổng input<div class="value">{input_tokens:,}</div></div><div class="card">Tổng output<div class="value">{output_tokens:,}</div></div><div class="card">10.000 issue/tháng<div class="value">${monthly_cost:.4f}</div></div></div>
<h2>Giả định giá</h2><ul><li>Input cache miss: $0.14 / 1 triệu token.</li><li>Output: $0.28 / 1 triệu token.</li><li>Kịch bản bảo thủ: toàn bộ input là cache miss.</li></ul>
<p class="formula">Chi phí = 10.000 × ((input × 0,14) + (output × 0,28)) / 1.000.000</p>
<p>Nguồn: <a href="https://api-docs.deepseek.com/quick_start/pricing/">DeepSeek Models &amp; Pricing</a>. Giá là giả định và có thể thay đổi.</p></main></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
