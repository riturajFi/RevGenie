from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from urllib import request

import experiment_harness.logger as logger
from pydantic import BaseModel, Field


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_CONTEXTS_PATH = THIS_DIR / "data" / "tester_project_contexts.json"
DEFAULT_SCENARIOS_PATH = THIS_DIR / "data" / "tester_scenarios.json"
DEFAULT_API_URL = "http://127.0.0.1:8000/workflows/messages"


class ProjectContext(BaseModel):
    project_context_id: str
    project_name: str
    system_under_test: str
    testing_instructions: list[str] = Field(default_factory=list)
    global_guardrails: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
    scenario_id: str
    opening_message: str
    borrower_profile: str
    borrower_intent: str
    reply_style_rules: list[str] = Field(default_factory=list)
    stop_condition: str
    expected_path_notes: str | None = None
    follow_up_messages: list[str] = Field(default_factory=list)


class WorkflowMessageResponse(BaseModel):
    workflow_id: str
    reply: str | None = None
    stage: str
    final_result: str | None = None


class TesterRunResult(BaseModel):
    workflow_id: str
    borrower_id: str
    scenario_id: str
    turn_count: int
    stop_reason: str


class ProjectContextRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, project_context_id: str) -> ProjectContext:
        payload = json.loads(self.path.read_text())
        for item in payload:
            if item["project_context_id"] == project_context_id:
                return ProjectContext.model_validate(item)
        raise KeyError(f"Unknown project context: {project_context_id}")


class ScenarioRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, scenario_id: str) -> Scenario:
        payload = json.loads(self.path.read_text())
        for item in payload:
            if item["scenario_id"] == scenario_id:
                return Scenario.model_validate(item)
        raise KeyError(f"Unknown scenario: {scenario_id}")


@dataclass
class TesterAgent:
    api_url: str = DEFAULT_API_URL
    project_context_repository: ProjectContextRepository = ProjectContextRepository(DEFAULT_PROJECT_CONTEXTS_PATH)
    scenario_repository: ScenarioRepository = ScenarioRepository(DEFAULT_SCENARIOS_PATH)

    def run(
        self,
        borrower_id: str,
        workflow_id: str,
        max_turns: int,
        project_context_id: str | None = None,
        scenario_id: str | None = None,
        project_context: ProjectContext | None = None,
        scenario: Scenario | None = None,
    ) -> TesterRunResult:
        project_context = project_context or self.project_context_repository.get(project_context_id or "")
        scenario = scenario or self.scenario_repository.get(scenario_id or "")

        turn_count = 0
        borrower_message = scenario.opening_message
        follow_up_index = 0
        stop_reason = "max_turns_reached"

        while turn_count < max_turns:
            logger.log(
                borrower_message,
                experiment_id=project_context.project_context_id,
                workflow_id=workflow_id,
                actor="borrower",
            )
            response = self._post_message(
                borrower_id=borrower_id,
                workflow_id=workflow_id,
                message=borrower_message,
            )
            turn_count += 1

            if response.final_result:
                stop_reason = "system_ended_conversation"
                break
            if response.stage == "FINAL_NOTICE":
                stop_reason = "final_notice_stage_reached"
                break
            if self._system_clearly_ended(response.reply):
                stop_reason = "system_clearly_ended_conversation"
                break
            if follow_up_index >= len(scenario.follow_up_messages):
                stop_reason = "scenario_goal_reached"
                break

            borrower_message = self._build_next_message(
                project_context=project_context,
                scenario=scenario,
                system_reply=response.reply,
                follow_up_index=follow_up_index,
            )
            follow_up_index += 1

        return TesterRunResult(
            workflow_id=workflow_id,
            borrower_id=borrower_id,
            scenario_id=scenario.scenario_id,
            turn_count=turn_count,
            stop_reason=stop_reason,
        )

    def _build_next_message(
        self,
        project_context: ProjectContext,
        scenario: Scenario,
        system_reply: str | None,
        follow_up_index: int,
    ) -> str:
        _ = project_context
        _ = system_reply
        return scenario.follow_up_messages[follow_up_index]

    def _post_message(
        self,
        borrower_id: str,
        workflow_id: str,
        message: str,
    ) -> WorkflowMessageResponse:
        payload = json.dumps(
            {
                "borrower_id": borrower_id,
                "workflow_id": workflow_id,
                "message": message,
            }
        ).encode("utf-8")
        http_request = request.Request(
            self.api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request) as response:
            return WorkflowMessageResponse.model_validate(json.loads(response.read().decode("utf-8")))

    def _system_clearly_ended(self, reply: str | None) -> bool:
        if not reply:
            return False
        normalized = reply.lower()
        return "conversation is now closed" in normalized or "this case is closed" in normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one tester scenario against the workflow API")
    parser.add_argument("--project-context-id", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--borrower-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--max-turns", type=int, default=5)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()

    agent = TesterAgent(api_url=args.api_url)
    result = agent.run(
        project_context_id=args.project_context_id,
        scenario_id=args.scenario_id,
        borrower_id=args.borrower_id,
        workflow_id=args.workflow_id,
        max_turns=args.max_turns,
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
