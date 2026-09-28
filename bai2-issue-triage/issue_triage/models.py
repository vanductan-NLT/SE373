"""Validated application contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class IssueTriage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["classified", "insufficient_data", "out_of_scope"]
    severity: Literal["P0", "P1", "P2", "P3"] | None
    component: str | None
    needs_urgent_response: bool
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("component")
    @classmethod
    def normalize_component(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower() or None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason không được để trống")
        return value

    @model_validator(mode="after")
    def validate_invariants(self) -> "IssueTriage":
        if self.status == "classified":
            if self.severity is None:
                raise ValueError("classified yêu cầu severity khác null")
            if self.needs_urgent_response != (self.severity in {"P0", "P1"}):
                raise ValueError("needs_urgent_response phải true chỉ với P0/P1")
        elif self.severity is not None or self.needs_urgent_response:
            raise ValueError("issue chưa classified phải có severity=null và không khẩn cấp")
        return self


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["classification", "tool_request", "final_response"]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ToolTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call_id: str
    name: str
    arguments: dict[str, Any]
    result: dict[str, str]


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triage: IssueTriage
    owner: str | None
    tool_traces: tuple[ToolTrace, ...] = ()
    final_response: str
    usage: tuple[UsageRecord, ...]

    @property
    def total_input_tokens(self) -> int:
        return sum(item.input_tokens for item in self.usage)

    @property
    def total_output_tokens(self) -> int:
        return sum(item.output_tokens for item in self.usage)
