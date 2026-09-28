import pytest
from pydantic import ValidationError
from issue_triage.models import IssueTriage


@pytest.mark.parametrize(("severity", "urgent"), [("P0", True), ("P1", True), ("P2", False), ("P3", False)])
def test_all_severities(severity, urgent):
    item = IssueTriage(status="classified", severity=severity, component=" Payment ", needs_urgent_response=urgent, reason="Đủ dữ liệu.")
    assert item.component == "payment"


@pytest.mark.parametrize("status", ["insufficient_data", "out_of_scope"])
def test_non_classified(status):
    assert IssueTriage(status=status, severity=None, component=None, needs_urgent_response=False, reason="Không phân loại.").severity is None


@pytest.mark.parametrize("payload", [
    {"status":"classified","severity":"P9","component":"payment","needs_urgent_response":False,"reason":"x"},
    {"status":"classified","severity":"P0","component":"payment","reason":"x"},
    {"status":"classified","severity":"P0","component":"payment","needs_urgent_response":True,"reason":"x","extra":1},
    {"status":"classified","severity":None,"component":"payment","needs_urgent_response":False,"reason":"x"},
    {"status":"out_of_scope","severity":"P3","component":None,"needs_urgent_response":False,"reason":"x"},
])
def test_invalid_payload(payload):
    with pytest.raises(ValidationError): IssueTriage.model_validate(payload)
