from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from experiment_harness.prompt_management_service.prompt_storage import (
    PromptStorageVersion,
    json_prompt_storage_service,
)

app = FastAPI(title="Experiment Harness Prompt Manager")
prompt_service = json_prompt_storage_service


class CreatePromptVersionRequest(BaseModel):
    prompt_text: str
    parent_version_id: str | None = None
    diff_summary: str | None = None


class ActivatePromptVersionRequest(BaseModel):
    version_id: str


class RollbackPromptVersionRequest(BaseModel):
    version_id: str


class PromptVersionResponse(BaseModel):
    id: int
    agent_id: str
    version_id: str
    parent_version_id: str | None
    prompt_text: str
    diff_summary: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, record: PromptStorageVersion) -> "PromptVersionResponse":
        return cls(
            id=record.id,
            agent_id=record.agent_id,
            version_id=record.version_id,
            parent_version_id=record.parent_version_id,
            prompt_text=record.prompt_text,
            diff_summary=record.diff_summary,
            created_at=record.created_at,
        )


class ActivePromptResponse(BaseModel):
    agent_id: str
    version_id: str
    prompt_text: str


class ActivatePromptResponse(BaseModel):
    agent_id: str
    active_version_id: str


@app.get("/prompts/{agent_id}/active", response_model=ActivePromptResponse)
def get_active_prompt(agent_id: str) -> ActivePromptResponse:
    try:
        record = prompt_service.get_active_prompt(agent_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return ActivePromptResponse(
        agent_id=record.agent_id,
        version_id=record.version_id,
        prompt_text=record.prompt_text,
    )


@app.get("/prompts/{agent_id}/history", response_model=list[PromptVersionResponse])
def get_prompt_history(agent_id: str) -> list[PromptVersionResponse]:
    try:
        records = prompt_service.get_prompt_history(agent_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return [PromptVersionResponse.from_record(record) for record in records]


@app.post(
    "/prompts/{agent_id}/versions",
    response_model=PromptVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_version(agent_id: str, request: CreatePromptVersionRequest) -> PromptVersionResponse:
    try:
        record = prompt_service.create_prompt_version(
            agent_id=agent_id,
            prompt_text=request.prompt_text,
            parent_version_id=request.parent_version_id,
            diff_summary=request.diff_summary,
        )
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return PromptVersionResponse.from_record(record)


@app.post("/prompts/{agent_id}/activate", response_model=ActivatePromptResponse)
def activate_prompt_version(agent_id: str, request: ActivatePromptVersionRequest) -> ActivatePromptResponse:
    try:
        active_version_id = prompt_service.activate_version(agent_id, request.version_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return ActivatePromptResponse(agent_id=agent_id, active_version_id=active_version_id)


@app.post("/prompts/{agent_id}/rollback", response_model=ActivatePromptResponse)
def rollback_prompt_version(agent_id: str, request: RollbackPromptVersionRequest) -> ActivatePromptResponse:
    try:
        active_version_id = prompt_service.rollback(agent_id, request.version_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return ActivatePromptResponse(agent_id=agent_id, active_version_id=active_version_id)
