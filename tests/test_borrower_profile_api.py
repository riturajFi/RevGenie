from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import borrower_profile as borrower_profile_api
from app.main import app
from app.services.borrower_profile import FileBorrowerProfileService


def test_create_borrower_profile_generates_borrower_id(tmp_path, monkeypatch) -> None:
    storage_path = tmp_path / "borrower_profiles.json"
    monkeypatch.setattr(
        borrower_profile_api,
        "service",
        FileBorrowerProfileService(file_path=str(storage_path)),
    )

    client = TestClient(app)
    response = client.post(
        "/borrower-profiles",
        json={
            "full_name": "Test Borrower",
            "phone_number": "+919900009999",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["borrower_id"].startswith("b_")
    assert payload["full_name"] == "Test Borrower"
    assert payload["phone_number"] == "+919900009999"
