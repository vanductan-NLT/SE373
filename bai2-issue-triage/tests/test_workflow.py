import json
from types import SimpleNamespace
import pytest

from issue_triage.tools import ToolValidationError
from issue_triage.workflow import ModelOutputError, TriageWorkflow


def response(content=None, tool_calls=None, prompt_tokens=10, completion_tokens=5):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))], usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens))


def tool_call(call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name="get_component_owner", arguments='{"component":"payment"}'))


class FakeCompletions:
    def __init__(self, responses): self.responses=list(responses); self.calls=[]
    def create(self, **kwargs): self.calls.append(kwargs); return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses): self.chat=SimpleNamespace(completions=FakeCompletions(responses))


def triage_json(status="classified", severity="P0", component="payment", urgent=True):
    return json.dumps({"status":status,"severity":severity,"component":component,"needs_urgent_response":urgent,"reason":"Ảnh hưởng toàn bộ thanh toán."})


def test_full_workflow():
    client=FakeClient([response(triage_json(),prompt_tokens=100,completion_tokens=40), response(tool_calls=[tool_call()],prompt_tokens=60,completion_tokens=10), response("P0 do checkout-platform xử lý.",prompt_tokens=80,completion_tokens=15)])
    result=TriageWorkflow(client).run("Mọi thanh toán đều lỗi.")
    assert result.owner=="checkout-platform"; assert result.total_input_tokens==240; assert result.total_output_tokens==65
    assert len(client.chat.completions.calls)==3
    assert client.chat.completions.calls[0]["response_format"]=={"type":"json_object"}
    assert all(x["extra_body"]=={"thinking":{"type":"disabled"}} for x in client.chat.completions.calls)


@pytest.mark.parametrize("status", ["insufficient_data","out_of_scope"])
def test_non_classified_skips_tool(status):
    client=FakeClient([response(triage_json(status,None,None,False))]); result=TriageWorkflow(client).run("Không rõ lỗi.")
    assert result.owner is None; assert result.tool_traces==(); assert len(client.chat.completions.calls)==1


def test_unknown_component_skips_tool():
    client=FakeClient([response(triage_json("classified","P2","profile",False))])
    assert TriageWorkflow(client).run("Avatar lỗi.").owner is None


def test_multiple_tools_rejected():
    client=FakeClient([response(triage_json()), response(tool_calls=[tool_call("a"),tool_call("b")])])
    with pytest.raises(ToolValidationError): TriageWorkflow(client).run("Thanh toán lỗi.")


@pytest.mark.parametrize("content", ["not-json",'{"status":"classified"}',None])
def test_bad_output(content):
    with pytest.raises(ModelOutputError): TriageWorkflow(FakeClient([response(content)])).run("Thanh toán lỗi.")


def test_empty_input_no_api_call():
    client=FakeClient([])
    with pytest.raises(ValueError): TriageWorkflow(client).run("  ")
    assert client.chat.completions.calls==[]
