from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from meta_eval_service.service import MetaEvaluatorApplyResult, MetaEvaluatorService

app = FastAPI(title="Loop 2 Meta Evaluation")
service = MetaEvaluatorService()


class MetaEvalApplyRequest(BaseModel):
    before_experiment_id: str
    after_experiment_id: str
    metrics_key: str
    lender_id: str | None = None
    force_activate: bool = True


@app.post("/meta-eval/apply", response_model=MetaEvaluatorApplyResult)
def apply_meta_eval(request: MetaEvalApplyRequest) -> MetaEvaluatorApplyResult:
    return service.apply_meta_change(
        before_experiment_id=request.before_experiment_id,
        after_experiment_id=request.after_experiment_id,
        metrics_key=request.metrics_key,
        lender_id=request.lender_id,
        force_activate=request.force_activate,
    )
