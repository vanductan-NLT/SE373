"""DeepSeek workflow with application-side structured output and tool control."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .models import IssueTriage, ToolTrace, UsageRecord, WorkflowResult
from .prompts import FINAL_SYSTEM_PROMPT, classification_messages, tool_messages
from .tools import COMPONENT_OWNERS, GET_COMPONENT_OWNER_TOOL, ToolValidationError, execute_tool_call


class ModelOutputError(RuntimeError):
    pass


def validate_issue_text(issue: str) -> str:
    issue = issue.strip()
    if not issue:
        raise ValueError("Mô tả issue không được để trống.")
    return issue


def _usage(response: Any, stage: str) -> UsageRecord:
    usage = getattr(response, "usage", None)
    return UsageRecord(
        stage=stage,
        input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
    )


class TriageWorkflow:
    def __init__(self, client: Any, model: str = "deepseek-flash") -> None:
        self.client = client
        self.model = model

    def _create(self, **kwargs: Any) -> Any:
        return self.client.chat.completions.create(
            model=self.model,
            extra_body={"thinking": {"type": "disabled"}},
            **kwargs,
        )

    def classify(self, issue: str) -> tuple[IssueTriage, UsageRecord]:
        response = self._create(
            messages=classification_messages(issue),
            response_format={"type": "json_object"},
            max_tokens=400,
        )
        content = response.choices[0].message.content
        if not content:
            raise ModelOutputError("Model không trả nội dung phân loại.")
        try:
            triage = IssueTriage.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as error:
            raise ModelOutputError(f"IssueTriage không hợp lệ: {error}") from error
        return triage, _usage(response, "classification")

    def run(self, issue: str) -> WorkflowResult:
        issue = validate_issue_text(issue)
        triage, first_usage = self.classify(issue)
        usage = [first_usage]
        if triage.status != "classified" or triage.component not in COMPONENT_OWNERS:
            return WorkflowResult(
                triage=triage, owner=None, final_response=triage.reason, usage=tuple(usage)
            )

        messages: list[dict[str, Any]] = tool_messages(issue, triage)
        tool_response = self._create(
            messages=messages,
            tools=[GET_COMPONENT_OWNER_TOOL],
            tool_choice={"type": "function", "function": {"name": "get_component_owner"}},
            max_tokens=200,
        )
        usage.append(_usage(tool_response, "tool_request"))
        assistant = tool_response.choices[0].message
        tool_calls = assistant.tool_calls or []
        if len(tool_calls) != 1:
            raise ToolValidationError(
                f"Workflow chỉ cho phép đúng một tool call, model trả {len(tool_calls)}."
            )
        call = tool_calls[0]
        arguments, tool_result = execute_tool_call(call.function.name, call.function.arguments)
        trace = ToolTrace(
            call_id=call.id,
            name=call.function.name,
            arguments=arguments,
            result=tool_result,
        )
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": assistant.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                },
                {"role": "system", "content": FINAL_SYSTEM_PROMPT},
            ]
        )
        final_response = self._create(messages=messages, max_tokens=300)
        usage.append(_usage(final_response, "final_response"))
        final_content = final_response.choices[0].message.content
        if not final_content:
            raise ModelOutputError("Model không trả final response.")
        return WorkflowResult(
            triage=triage,
            owner=tool_result["owner"],
            tool_traces=(trace,),
            final_response=final_content.strip(),
            usage=tuple(usage),
        )
