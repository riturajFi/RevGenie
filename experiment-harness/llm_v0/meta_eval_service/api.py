from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from meta_eval_management_service.service import MetaEvalRunRecord
from meta_eval_service.service import MetaEvaluatorService

app = FastAPI(title="Loop 2 Meta Evaluation")
service = MetaEvaluatorService()


class MetaEvalApplyRequest(BaseModel):
    before_experiment_id: str
    after_experiment_id: str
    metrics_key: str
    lender_id: str | None = None
    force_activate: bool = True


@app.post("/meta-eval/judge", response_model=MetaEvalRunRecord)
@app.post("/meta-eval/apply", response_model=MetaEvalRunRecord)
def apply_meta_eval(request: MetaEvalApplyRequest) -> MetaEvalRunRecord:
    return service.judge(
        before_experiment_id=request.before_experiment_id,
        after_experiment_id=request.after_experiment_id,
        metrics_key=request.metrics_key,
        lender_id=request.lender_id,
        force_activate=request.force_activate,
    )


@app.get("/meta-eval/runs/{run_id}", response_model=MetaEvalRunRecord | None)
def get_meta_eval_run(run_id: str) -> MetaEvalRunRecord | None:
    return service.get_run(run_id)


@app.get("/meta-eval/runs", response_model=list[MetaEvalRunRecord])
def list_meta_eval_runs() -> list[MetaEvalRunRecord]:
    return service.list_runs()
