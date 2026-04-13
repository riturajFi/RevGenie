from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from meta_eval_service.company_policy import CompanyPolicy, CompanyPolicyManager
from meta_eval_service.service import MetaEvaluatorApplyResult, MetaEvaluatorService

app = FastAPI(title="Loop 2 Meta Evaluation")
policy_manager = CompanyPolicyManager()
service = MetaEvaluatorService(company_policy_manager=policy_manager)


class MetaEvalApplyRequest(BaseModel):
    before_experiment_id: str
    after_experiment_id: str
    metrics_key: str
    force_activate: bool = True


class MetaEvalPolicyRequest(BaseModel):
    policy_text: str


@app.post("/meta-eval/apply", response_model=MetaEvaluatorApplyResult)
def apply_meta_eval(request: MetaEvalApplyRequest) -> MetaEvaluatorApplyResult:
    return service.apply_meta_change(
        before_experiment_id=request.before_experiment_id,
        after_experiment_id=request.after_experiment_id,
        metrics_key=request.metrics_key,
        force_activate=request.force_activate,
    )


@app.get("/meta-eval/policy", response_model=CompanyPolicy)
def get_meta_eval_policy() -> CompanyPolicy:
    return policy_manager.get_policy()


@app.put("/meta-eval/policy", response_model=CompanyPolicy)
def set_meta_eval_policy(request: MetaEvalPolicyRequest) -> CompanyPolicy:
    return policy_manager.set_policy(request.policy_text)
