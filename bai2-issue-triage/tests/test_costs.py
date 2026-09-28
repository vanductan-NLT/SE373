from issue_triage.costs import build_cost_report, estimate_cost
from issue_triage.models import IssueTriage, UsageRecord, WorkflowResult


def test_cost_formula(): assert estimate_cost(1000,500,10000)==2.8


def test_html(tmp_path):
    result=WorkflowResult(triage=IssueTriage(status="classified",severity="P2",component="search",needs_urgent_response=False,reason="Lỗi hạn chế."),owner="search-platform",final_response="OK",usage=(UsageRecord(stage="classification",input_tokens=100,output_tokens=20),))
    path=tmp_path/"cost.html"; build_cost_report(path,"Tìm kiếm lỗi",result); html=path.read_text(encoding="utf-8")
    assert "100" in html and "20" in html and "$0.1960" in html
