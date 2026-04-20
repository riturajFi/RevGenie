from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.domain.borrower_case import CaseStatus, ResolutionMode, Stage
from app.services.eval_performance import EvalPerformanceDataset, EvalPerformanceService
from app.services.prompt_evolution import PromptEvolutionResponse, PromptEvolutionService
from app.services.borrower_case import FileBorrowerCaseService
from app.services.chat_message import get_chat_message_service
from app.services.simulation_run_history import SimulationRunHistoryService
from evals.compliance_management_service.service import ComplianceConfig, compliance_config_service
from evals.judge_service.service import JudgeResult, JudgeService
from evals.logging_service import TranscriptLoggingService
from evals.logging_service.logger import LogEvent
from evals.meta_eval_management_service.service import MetaEvalRunRecord
from evals.meta_eval_service.service import MetaEvaluatorService
from evals.prompt_change_service.service import PromptChangeApplyResult, PromptChangeProposer
from evals.prompt_management_service.prompt_storage import json_prompt_storage_service
from evals.tester_service import DEFAULT_SCENARIOS_PATH, Scenario, ScenarioRepository, TesterAgent, TesterRunResult


router = APIRouter(prefix="/evals", tags=["evals"])

scenario_repository = ScenarioRepository(DEFAULT_SCENARIOS_PATH)
borrower_case_service = FileBorrowerCaseService()
chat_message_service = get_chat_message_service()
simulation_executor = ThreadPoolExecutor(max_workers=2)
simulation_lock = Lock()
simulation_runs: dict[str, dict] = {}
judge_service = JudgeService()
prompt_change_proposer = PromptChangeProposer()
meta_evaluator_service = MetaEvaluatorService()
run_history_service = SimulationRunHistoryService()
performance_service = EvalPerformanceService(
    run_history_service=run_history_service,
)
prompt_evolution_service = PromptEvolutionService()
logging_service = TranscriptLoggingService()


class ScenarioCreateRequest(BaseModel):
    scenario_id: str
    borrower_id: str | None = None
    opening_message: str
    scenario_description: str | None = None
    borrower_profile: str
    borrower_intent: str
    reply_style_rules: list[str] = Field(default_factory=list)
    stop_condition: str
    expected_path_notes: str | None = None
    follow_up_messages: list[str] = Field(default_factory=list)


class SimulationStartRequest(BaseModel):
    borrower_id: str
    scenario_id: str
    project_context_id: str = "collections_v1"
    max_turns: int = Field(default=50, ge=1, le=200)
    workflow_id: str | None = None
    experiment_id: str | None = None
    reset_case: bool = True
    clear_experiment_log: bool = True


class SimulationStartResponse(BaseModel):
    run_id: str
    workflow_id: str
    experiment_id: str
    status: str


class SimulationStatusResponse(BaseModel):
    run_id: str
    workflow_id: str
    experiment_id: str
    status: str
    result: TesterRunResult | None = None
    error: str | None = None
    started_at: str
    finished_at: str | None = None


class TranscriptEventResponse(BaseModel):
    id: int
    experiment_id: str | None = None
    workflow_id: str | None = None
    actor: str | None
    message_text: str
    structured_payload: dict | None = None
    created_at: str


class ConversationLogSummaryResponse(BaseModel):
    workflow_id: str
    borrower_id: str | None = None
    lender_id: str | None = None
    stage: str | None = None
    case_status: str | None = None
    message_count: int
    first_message_at: str | None = None
    last_message_at: str | None = None
    last_message_text: str | None = None


class ConversationMessageResponse(BaseModel):
    id: str
    workflow_id: str
    borrower_id: str
    agent_id: str
    sender_type: str
    message_text: str
    visible_to_borrower: bool
    created_at: str


class EvaluateSimulationRequest(BaseModel):
    metrics_key: str = "collections_agent_eval"
    lender_id: str | None = None
    persist: bool = True


class EvaluateSimulationResponse(BaseModel):
    run_id: str
    workflow_id: str
    experiment_id: str
    result: JudgeResult


class PromptChangeBatchRequest(BaseModel):
    target_agent_ids: list[str] = Field(default_factory=lambda: ["agent_1", "agent_2", "agent_3"])
    force_activate: bool = True


class PromptChangeBatchResponse(BaseModel):
    run_id: str
    workflow_id: str
    experiment_id: str
    results: list[PromptChangeApplyResult]


class PromptVersionActivateRequest(BaseModel):
    agent_id: str
    version_id: str


class PromptVersionActivateResponse(BaseModel):
    run_id: str
    agent_id: str
    active_version_id: str


class PromptVersionActivateDirectResponse(BaseModel):
    agent_id: str
    active_version_id: str


class PromptVersionRevertRequest(BaseModel):
    agent_id: str
    revert_to_version_id: str


class PromptVersionRevertResponse(BaseModel):
    run_id: str
    agent_id: str
    active_version_id: str


class ComplianceUpdateRequest(BaseModel):
    rules_text: str


class MetaEvalRunRequest(BaseModel):
    metrics_key: str = "collections_agent_eval"
    lender_id: str | None = "nira"


class MetaEvalLatestPairResponse(BaseModel):
    before_experiment_id: str | None = None
    after_experiment_id: str | None = None
    total_evaluated_experiments: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{now}_{uuid4().hex[:6]}"


def _clear_experiment_log(experiment_id: str) -> None:
    for suffix in (".jsonl", ".json"):
        path = Path("data/chats/experiments") / f"{experiment_id}{suffix}"
        if path.exists():
            path.unlink()


def _reset_case_for_simulation(borrower_id: str, workflow_id: str) -> None:
    borrower_case = borrower_case_service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise KeyError(f"Borrower case not found for {borrower_id}")

    borrower_case.workflow_id = workflow_id
    borrower_case.stage = Stage.ASSESSMENT
    borrower_case.case_status = CaseStatus.OPEN
    borrower_case.final_disposition = None
    borrower_case.latest_handoff_summary = None
    borrower_case.attributes = {}
    borrower_case.resolution_mode = ResolutionMode.CHAT
    borrower_case.resolution_call_id = None
    borrower_case.resolution_call_status = None

    borrower_case_service.update_borrower_case(borrower_id, borrower_case)


def _run_simulation_job(
    run_id: str,
    borrower_id: str,
    workflow_id: str,
    experiment_id: str,
    project_context_id: str,
    scenario_id: str,
    max_turns: int,
) -> None:
    with simulation_lock:
        simulation_runs[run_id]["status"] = "running"
    run_history_service.update_status(run_id=run_id, status="running")

    try:
        tester = TesterAgent()
        result = tester.run(
            borrower_id=borrower_id,
            workflow_id=workflow_id,
            experiment_id=experiment_id,
            project_context_id=project_context_id,
            scenario_id=scenario_id,
            max_turns=max_turns,
        )
        with simulation_lock:
            simulation_runs[run_id]["status"] = "completed"
            simulation_runs[run_id]["result"] = result
            simulation_runs[run_id]["finished_at"] = _utc_now()
        run_history_service.update_status(
            run_id=run_id,
            status="completed",
            finished_at=simulation_runs[run_id]["finished_at"],
            error=None,
        )
    except Exception as error:
        with simulation_lock:
            simulation_runs[run_id]["status"] = "failed"
            simulation_runs[run_id]["error"] = str(error)
            simulation_runs[run_id]["finished_at"] = _utc_now()
        run_history_service.update_status(
            run_id=run_id,
            status="failed",
            finished_at=simulation_runs[run_id]["finished_at"],
            error=str(error),
        )


@router.get("/scenarios", response_model=list[Scenario])
def list_scenarios() -> list[Scenario]:
    return scenario_repository.list()


@router.post("/scenarios", response_model=Scenario, status_code=status.HTTP_201_CREATED)
def create_scenario(request: ScenarioCreateRequest) -> Scenario:
    scenario = Scenario.model_validate(request.model_dump(mode="python"))
    try:
        return scenario_repository.create(scenario)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/simulations/start", response_model=SimulationStartResponse)
def start_simulation(request: SimulationStartRequest) -> SimulationStartResponse:
    try:
        scenario_repository.get(request.scenario_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    run_id = _generate_id("sim")
    workflow_id = request.workflow_id or _generate_id("wf")
    experiment_id = request.experiment_id or _generate_id("exp")
    borrower_case = borrower_case_service.get_borrower_case(request.borrower_id)

    if request.reset_case:
        try:
            _reset_case_for_simulation(request.borrower_id, workflow_id)
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        borrower_case = borrower_case_service.get_borrower_case(request.borrower_id)

    if request.clear_experiment_log:
        _clear_experiment_log(experiment_id)

    with simulation_lock:
        simulation_runs[run_id] = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "experiment_id": experiment_id,
            "status": "queued",
            "result": None,
            "error": None,
            "started_at": _utc_now(),
            "finished_at": None,
        }
    run_history_service.create_run(
        run_id=run_id,
        workflow_id=workflow_id,
        experiment_id=experiment_id,
        borrower_id=request.borrower_id,
        scenario_id=request.scenario_id,
        lender_id=borrower_case.lender_id if borrower_case is not None else None,
        status="queued",
        started_at=simulation_runs[run_id]["started_at"],
    )

    simulation_executor.submit(
        _run_simulation_job,
        run_id,
        request.borrower_id,
        workflow_id,
        experiment_id,
        request.project_context_id,
        request.scenario_id,
        request.max_turns,
    )

    return SimulationStartResponse(
        run_id=run_id,
        workflow_id=workflow_id,
        experiment_id=experiment_id,
        status="queued",
    )


@router.get("/simulations/{run_id}", response_model=SimulationStatusResponse)
def get_simulation_status(run_id: str) -> SimulationStatusResponse:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")

    return SimulationStatusResponse(
        run_id=record["run_id"],
        workflow_id=record["workflow_id"],
        experiment_id=record["experiment_id"],
        status=record["status"],
        result=record["result"],
        error=record["error"],
        started_at=record["started_at"],
        finished_at=record["finished_at"],
    )


@router.get("/simulations/{run_id}/events", response_model=list[TranscriptEventResponse])
def get_simulation_events(run_id: str) -> list[TranscriptEventResponse]:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")

    events: list[LogEvent] = logging_service.get_logs(record["experiment_id"])
    return [
        TranscriptEventResponse(
            id=event.id,
            experiment_id=event.experiment_id,
            workflow_id=event.workflow_id,
            actor=event.actor,
            message_text=event.message_text,
            structured_payload=event.structured_payload,
            created_at=event.created_at,
        )
        for event in events
    ]


@router.get("/conversations", response_model=list[ConversationLogSummaryResponse])
def list_conversation_logs() -> list[ConversationLogSummaryResponse]:
    borrower_cases_by_workflow = {
        borrower_case.workflow_id: borrower_case
        for borrower_case in borrower_case_service.list_borrower_cases()
    }
    simulation_workflow_ids = {run.workflow_id for run in run_history_service.list_runs()}
    grouped_messages: dict[str, list] = {}
    for message in chat_message_service.list_all_messages():
        if message.workflow_id in simulation_workflow_ids:
            continue
        grouped_messages.setdefault(message.workflow_id, []).append(message)

    responses: list[ConversationLogSummaryResponse] = []
    for workflow_id, messages in grouped_messages.items():
        messages = sorted(messages, key=lambda item: item.created_at)
        borrower_case = borrower_cases_by_workflow.get(workflow_id)
        responses.append(
            ConversationLogSummaryResponse(
                workflow_id=workflow_id,
                borrower_id=borrower_case.borrower_id if borrower_case is not None else messages[0].user_id,
                lender_id=borrower_case.lender_id if borrower_case is not None else None,
                stage=borrower_case.stage.value if borrower_case is not None else None,
                case_status=borrower_case.case_status.value if borrower_case is not None else None,
                message_count=len(messages),
                first_message_at=messages[0].created_at.isoformat(),
                last_message_at=messages[-1].created_at.isoformat(),
                last_message_text=messages[-1].message,
            )
        )
    return sorted(responses, key=lambda item: item.last_message_at or "", reverse=True)


@router.get("/conversations/{workflow_id}/messages", response_model=list[ConversationMessageResponse])
def get_conversation_messages(workflow_id: str) -> list[ConversationMessageResponse]:
    messages = [
        message
        for message in chat_message_service.list_all_messages()
        if message.workflow_id == workflow_id
    ]
    if not messages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return [
        ConversationMessageResponse(
            id=f"{index}_{message.agent_id}_{message.created_at.isoformat()}",
            workflow_id=message.workflow_id,
            borrower_id=message.user_id,
            agent_id=message.agent_id,
            sender_type=message.sender_type,
            message_text=message.message,
            visible_to_borrower=message.visible_to_borrower,
            created_at=message.created_at.isoformat(),
        )
        for index, message in enumerate(messages)
    ]


@router.post("/simulations/{run_id}/evaluate", response_model=EvaluateSimulationResponse)
def evaluate_simulation(run_id: str, request: EvaluateSimulationRequest) -> EvaluateSimulationResponse:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")
    if record["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulation must be completed before evaluation")

    try:
        lender_id = request.lender_id or record.get("lender_id")
        result = judge_service.judge_experiment(
            workflow_id=record["workflow_id"],
            metrics_key=request.metrics_key,
            lender_id=lender_id,
            persist=request.persist,
        )
        prompt_versions = _get_active_prompt_versions()
        run_history_service.append_evaluation(
            run_id=run_id,
            metrics_key=request.metrics_key,
            lender_id=lender_id,
            overall_score=result.overall_score,
            verdict=result.verdict,
            prompt_versions=prompt_versions,
        )
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return EvaluateSimulationResponse(
        run_id=run_id,
        workflow_id=record["workflow_id"],
        experiment_id=record["experiment_id"],
        result=result,
    )


@router.get("/performance", response_model=EvalPerformanceDataset)
def get_eval_performance(scenario_id: str | None = Query(default=None)) -> EvalPerformanceDataset:
    return performance_service.get_dataset(scenario_id=scenario_id)


@router.get("/prompt-evolution/{agent_id}", response_model=PromptEvolutionResponse)
def get_prompt_evolution(agent_id: str) -> PromptEvolutionResponse:
    try:
        return prompt_evolution_service.get_evolution(agent_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/prompt-evolution/activate", response_model=PromptVersionActivateDirectResponse)
def activate_prompt_version_direct(request: PromptVersionActivateRequest) -> PromptVersionActivateDirectResponse:
    try:
        active_version_id = json_prompt_storage_service.activate_version(request.agent_id, request.version_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return PromptVersionActivateDirectResponse(
        agent_id=request.agent_id,
        active_version_id=active_version_id,
    )


@router.get("/compliance", response_model=ComplianceConfig)
def get_compliance() -> ComplianceConfig:
    return compliance_config_service.get()


@router.put("/compliance", response_model=ComplianceConfig)
def update_compliance(request: ComplianceUpdateRequest) -> ComplianceConfig:
    return compliance_config_service.update(request.rules_text)


@router.post("/compliance/reset", response_model=ComplianceConfig)
def reset_compliance() -> ComplianceConfig:
    return compliance_config_service.reset_to_default()


@router.post("/simulations/{run_id}/prompt-changes/apply", response_model=PromptChangeBatchResponse)
def apply_prompt_changes(run_id: str, request: PromptChangeBatchRequest) -> PromptChangeBatchResponse:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")
    if record["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Simulation must be completed before proposing prompt changes",
        )

    results: list[PromptChangeApplyResult] = []
    try:
        for target_agent_id in request.target_agent_ids:
            result = prompt_change_proposer.apply_change(
                experiment_id=record["experiment_id"],
                target_agent_id=target_agent_id,
                force_activate=request.force_activate,
            )
            results.append(result)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return PromptChangeBatchResponse(
        run_id=run_id,
        workflow_id=record["workflow_id"],
        experiment_id=record["experiment_id"],
        results=results,
    )


@router.post("/simulations/{run_id}/prompt-changes/activate", response_model=PromptVersionActivateResponse)
def activate_prompt_change(run_id: str, request: PromptVersionActivateRequest) -> PromptVersionActivateResponse:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")

    try:
        active_version_id = json_prompt_storage_service.activate_version(request.agent_id, request.version_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return PromptVersionActivateResponse(
        run_id=run_id,
        agent_id=request.agent_id,
        active_version_id=active_version_id,
    )


@router.post("/simulations/{run_id}/prompt-changes/revert", response_model=PromptVersionRevertResponse)
def revert_prompt_change(run_id: str, request: PromptVersionRevertRequest) -> PromptVersionRevertResponse:
    with simulation_lock:
        record = simulation_runs.get(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation run not found")

    try:
        active_version_id = json_prompt_storage_service.rollback(request.agent_id, request.revert_to_version_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return PromptVersionRevertResponse(
        run_id=run_id,
        agent_id=request.agent_id,
        active_version_id=active_version_id,
    )


def _get_active_prompt_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for agent_id in ("agent_1", "agent_2", "agent_3"):
        try:
            versions[agent_id] = json_prompt_storage_service.get_active_prompt(agent_id).version_id
        except KeyError:
            continue
    return versions


def _get_latest_evaluated_experiment_ids(limit: int = 2) -> list[str]:
    evaluations: list[tuple[str, str]] = []
    for run in run_history_service.list_runs():
        if not run.evaluations:
            continue
        latest_evaluation = run.evaluations[-1]
        evaluations.append((latest_evaluation.created_at, run.experiment_id))

    evaluations.sort(key=lambda item: item[0], reverse=True)
    deduped_ids: list[str] = []
    seen: set[str] = set()
    for _, experiment_id in evaluations:
        if experiment_id in seen:
            continue
        seen.add(experiment_id)
        deduped_ids.append(experiment_id)
        if len(deduped_ids) >= limit:
            break
    return deduped_ids


@router.get("/meta-eval/latest-pair", response_model=MetaEvalLatestPairResponse)
def get_latest_meta_eval_pair() -> MetaEvalLatestPairResponse:
    latest_ids = _get_latest_evaluated_experiment_ids(limit=2)
    if len(latest_ids) < 2:
        return MetaEvalLatestPairResponse(
            before_experiment_id=None,
            after_experiment_id=None,
            total_evaluated_experiments=len(latest_ids),
        )
    return MetaEvalLatestPairResponse(
        before_experiment_id=latest_ids[1],
        after_experiment_id=latest_ids[0],
        total_evaluated_experiments=len(latest_ids),
    )


@router.post("/meta-eval/run", response_model=MetaEvalRunRecord)
def run_meta_eval(request: MetaEvalRunRequest) -> MetaEvalRunRecord:
    latest_ids = _get_latest_evaluated_experiment_ids(limit=2)
    if len(latest_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="At least two evaluated experiments are required for meta evaluation.",
        )

    try:
        return meta_evaluator_service.judge(
            before_experiment_id=latest_ids[1],
            after_experiment_id=latest_ids[0],
            metrics_key=request.metrics_key,
            lender_id=request.lender_id,
        )
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.get("/meta-eval/runs", response_model=list[MetaEvalRunRecord])
def list_meta_eval_runs() -> list[MetaEvalRunRecord]:
    return meta_evaluator_service.list_runs()
