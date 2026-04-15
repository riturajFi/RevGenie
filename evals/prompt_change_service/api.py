from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from evals.prompt_change_service.service import (
    PromptChangeApplyRequest,
    PromptChangeApplyResult,
    PromptChangeProposer,
)

app = FastAPI(title="Prompt Change Proposer")
proposer = PromptChangeProposer()


@app.post("/prompt-changes/apply", response_model=PromptChangeApplyResult)
def apply_prompt_change(request: PromptChangeApplyRequest) -> PromptChangeApplyResult:
    try:
        return proposer.apply_change(
            experiment_id=request.experiment_id,
            target_agent_id=request.target_agent_id,
            force_activate=request.force_activate,
        )
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
