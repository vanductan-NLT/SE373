#!/usr/bin/env python3
"""CLI for Issue Triage."""

import argparse
import json
from pathlib import Path

from issue_triage.config import ConfigurationError, Settings
from issue_triage.costs import build_cost_report
from issue_triage.workflow import TriageWorkflow

DEFAULT_ISSUE = "Nút thanh toán trả HTTP 500 với mọi thẻ Visa từ 14:30; tất cả người dùng đều không thể hoàn tất thanh toán."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", default=DEFAULT_ISSUE)
    parser.add_argument("--write-cost-report", action="store_true")
    args = parser.parse_args()
    try:
        settings = Settings.from_environment()
        result = TriageWorkflow(settings.create_client(), settings.model).run(args.issue)
    except (ConfigurationError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}")
        return 1
    except Exception as error:
        print(f"ERROR: DeepSeek API không hoàn tất yêu cầu: {type(error).__name__}")
        return 1
    print("=== IssueTriage đã validate ===")
    print(result.triage.model_dump_json(indent=2))
    for trace in result.tool_traces:
        print("\n=== tool_call ===")
        print(json.dumps({"id": trace.call_id, "name": trace.name, "arguments": trace.arguments}, ensure_ascii=False, indent=2))
        print("\n=== application executes ===")
        print(f"get_component_owner({trace.arguments['component']!r})")
        print("\n=== tool_result ===")
        print(json.dumps(trace.result, ensure_ascii=False, indent=2))
    print("\n=== final response ===\n" + result.final_response)
    print("\n=== token usage ===")
    for item in result.usage:
        print(f"{item.stage}: input={item.input_tokens}, output={item.output_tokens}")
    print(f"total: input={result.total_input_tokens}, output={result.total_output_tokens}")
    if args.write_cost_report:
        path = Path("docs/uoc_tinh_chi_phi.html")
        build_cost_report(path, args.issue, result)
        print(f"Đã cập nhật: {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
