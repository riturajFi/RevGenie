from __future__ import annotations

from app.domain.borrower_case import AgentStageOutcome, AgentTurnResult, BorrowerCase, CaseStatus, Stage
from app.orchestrator import activities
from app.orchestrator.models import ResolutionCallActivityInput


def _make_case() -> BorrowerCase:
    return BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": "b_voice",
                "workflow_id": "wf_voice",
                "loan_id_masked": "****1234",
                "lender_id": "nira",
                "stage": Stage.RESOLUTION,
                "case_status": CaseStatus.OPEN,
                "amount_due": 1000,
                "final_disposition": None,
            },
            "attributes": {
                "resolution_mode": "VOICE",
            },
            "latest_handoff_summary": "Assessment complete. Continue naturally.",
        }
    )


def test_finalize_resolution_call_uses_dedicated_call_analyzer(monkeypatch) -> None:
    borrower_case = _make_case()
    analyzer_called: dict[str, object] = {}

    class FakeResolutionAgent:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("ResolutionAgent should not be used for completed call analysis")

    class FakeResolutionCallAnalyzer:
        def __init__(self, lender_id: str | None = None, model: str | None = None) -> None:
            analyzer_called["lender_id"] = lender_id

        def analyze_completed_call(
            self,
            borrower_id: str,
            borrower_case: BorrowerCase,
            transcript: str,
        ) -> AgentTurnResult:
            analyzer_called["borrower_id"] = borrower_id
            analyzer_called["transcript"] = transcript
            return AgentTurnResult(
                reply="",
                stage_outcome=AgentStageOutcome.NO_DEAL,
                case_delta={},
                latest_handoff_summary="Voice call analyzed separately.",
            )

    class FakeBorrowerCaseStateService:
        def apply_delta(
            self,
            borrower_case: BorrowerCase,
            case_delta: dict,
            stage: Stage,
            latest_handoff_summary: str | None,
        ) -> BorrowerCase:
            borrower_case.latest_handoff_summary = latest_handoff_summary
            return borrower_case

    monkeypatch.setattr(activities, "ResolutionAgent", FakeResolutionAgent)
    monkeypatch.setattr(activities, "ResolutionCallAnalyzer", FakeResolutionCallAnalyzer)
    monkeypatch.setattr(activities, "borrower_case_state_service", FakeBorrowerCaseStateService())
    monkeypatch.setattr(activities, "_ensure_handoff_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(activities, "_append_message", lambda *args, **kwargs: None)

    result = activities.finalize_resolution_call(
        ResolutionCallActivityInput(
            borrower_case=borrower_case,
            call={
                "call_id": "call_123",
                "call_status": "ended",
                "transcript_object": [
                    {"role": "user", "content": "I can pay 500 today."},
                    {"role": "agent", "content": "I have recorded that."},
                ],
            },
        )
    )

    assert analyzer_called["lender_id"] == "nira"
    assert analyzer_called["borrower_id"] == "b_voice"
    assert analyzer_called["transcript"] == "BORROWER: I can pay 500 today.\nAGENT: I have recorded that."
    assert result.stage_result.latest_handoff_summary == "Voice call analyzed separately."
