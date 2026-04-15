from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from compliance_management_service.service import ComplianceConfig, compliance_config_service

app = FastAPI(title="Compliance Config")


class ComplianceUpdateRequest(BaseModel):
    rules_text: str


@app.get("/compliance", response_model=ComplianceConfig)
def get_compliance() -> ComplianceConfig:
    return compliance_config_service.get()


@app.put("/compliance", response_model=ComplianceConfig)
def update_compliance(request: ComplianceUpdateRequest) -> ComplianceConfig:
    return compliance_config_service.update(request.rules_text)


@app.post("/compliance/reset", response_model=ComplianceConfig)
def reset_compliance() -> ComplianceConfig:
    return compliance_config_service.reset_to_default()
