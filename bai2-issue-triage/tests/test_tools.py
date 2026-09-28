import pytest
from issue_triage.tools import ToolValidationError, execute_tool_call


def test_valid_tool():
    args, result = execute_tool_call("get_component_owner", '{"component":"payment"}')
    assert args == {"component":"payment"}; assert result["owner"] == "checkout-platform"


@pytest.mark.parametrize(("name","args"), [("delete_database",'{"component":"payment"}'), ("get_component_owner",'{"component":"billing"}'), ("get_component_owner",'{"component":12}'), ("get_component_owner",'{"component":"payment","force":true}'), ("get_component_owner","bad")])
def test_invalid_tool(name, args):
    with pytest.raises(ToolValidationError): execute_tool_call(name, args)
