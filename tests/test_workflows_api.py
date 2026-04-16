from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import workflows as workflows_api
from app.domain.borrower_case import BorrowerCase, CaseStatus, ResolutionMode, Stage
from app.main import app
from app.orchestrator.models import CollectionsWorkflowState
from app.services.borrower_case import FileBorrowerCaseService


def _make_case(borrower_id: str, workflow_id: str) -> BorrowerCase:
    return BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": borrower_id,
                "workflow_id": workflow_id,
                "loan_id_masked": "****1234",
                "lender_id": "nira",
                "stage": Stage.ASSESSMENT,
                "case_status": CaseStatus.OPEN,
                "case_type": ["SETTLEMENT_CANDIDATE"],
                "amount_due": 1000,
                "identity_verified": False,
                "next_allowed_actions": ["OFFER_PAYMENT_PLAN"],
                "final_disposition": None,
            },
            "attributes": {},
        }
    )


def test_borrower_messages_default_to_voice_resolution_mode(tmp_path, monkeypatch) -> None:
    storage_path = tmp_path / "borrower_cases.json"
    service = FileBorrowerCaseService(file_path=str(storage_path))
    service.create_borrower_case(_make_case("b_voice", "wf_voice"))
    monkeypatch.setattr(workflows_api, "borrower_case_service", service)

    captured: dict[str, object] = {}

    class FakeClient:
        async def execute_update_with_start_workflow(self, update_handler, update_input, start_workflow_operation):
            captured["update_handler"] = update_handler
            captured["update_input"] = update_input
            borrower_case = service.get_borrower_case("b_voice")
            assert borrower_case is not None
            borrower_case.resolution_mode = update_input.resolution_mode
            return CollectionsWorkflowState(
                borrower_case=borrower_case,
                last_agent_reply="voice-default",
                final_result=None,
            )

    async def fake_get_temporal_client():
        return FakeClient()

    monkeypatch.setattr(workflows_api, "get_temporal_client", fake_get_temporal_client)

    client = TestClient(app)
    response = client.post(
        "/workflows/messages",
        json={
            "borrower_id": "b_voice",
            "workflow_id": "wf_voice",
            "message": "hello",
        },
    )

    assert response.status_code == 200
    assert captured["update_input"].resolution_mode == ResolutionMode.VOICE
    assert response.json()["resolution_mode"] == "VOICE"


def test_tester_messages_default_to_chat_resolution_mode(tmp_path, monkeypatch) -> None:
    storage_path = tmp_path / "borrower_cases.json"
    service = FileBorrowerCaseService(file_path=str(storage_path))
    service.create_borrower_case(_make_case("b_chat", "wf_chat"))
    monkeypatch.setattr(workflows_api, "borrower_case_service", service)

    captured: dict[str, object] = {}

    class FakeClient:
        async def execute_update_with_start_workflow(self, update_handler, update_input, start_workflow_operation):
            captured["update_handler"] = update_handler
            captured["update_input"] = update_input
            borrower_case = service.get_borrower_case("b_chat")
            assert borrower_case is not None
            borrower_case.resolution_mode = update_input.resolution_mode
            return CollectionsWorkflowState(
                borrower_case=borrower_case,
                last_agent_reply="chat-default",
                final_result=None,
            )

    async def fake_get_temporal_client():
        return FakeClient()

    monkeypatch.setattr(workflows_api, "get_temporal_client", fake_get_temporal_client)

    client = TestClient(app)
    response = client.post(
        "/workflows/test/messages",
        json={
            "borrower_id": "b_chat",
            "workflow_id": "wf_chat",
            "message": "hello",
        },
    )

    assert response.status_code == 200
    assert captured["update_input"].resolution_mode == ResolutionMode.CHAT
    assert response.json()["resolution_mode"] == "CHAT"
