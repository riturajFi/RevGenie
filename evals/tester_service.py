from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from time import time_ns
from typing import Any, Callable
from urllib import request

from evals.logging_service import TranscriptLoggingService
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from app.domain.borrower_case import BorrowerCase, Stage
from app.services.borrower_profile import FileBorrowerProfileService
from app.services.borrower_case import FileBorrowerCaseService
from app.services.llm_factory import build_chat_llm


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT_CONTEXTS_PATH = REPO_ROOT / "data" / "evals" / "tester_project_contexts.json"
DEFAULT_SCENARIOS_PATH = REPO_ROOT / "data" / "evals" / "tester_scenarios.json"
DEFAULT_API_URL = "http://127.0.0.1:8000/workflows/test/messages"


class ProjectContext(BaseModel):
    project_context_id: str
    project_name: str
    system_under_test: str
    testing_instructions: list[str] = Field(default_factory=list)
    global_guardrails: list[str] = Field(default_factory=list)


class Scenario(BaseModel):
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


class WorkflowMessageResponse(BaseModel):
    workflow_id: str
    reply: str | None = None
    stage: str
    final_result: str | None = None


class TesterRunResult(BaseModel):
    experiment_id: str
    workflow_id: str
    borrower_id: str
    scenario_id: str
    turn_count: int
    stop_reason: str


class BorrowerTurnDecision(BaseModel):
    message: str


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

    def list(self) -> list[Scenario]:
        payload = json.loads(self.path.read_text())
        return [Scenario.model_validate(item) for item in payload]

    def get(self, scenario_id: str) -> Scenario:
        payload = json.loads(self.path.read_text())
        for item in payload:
            if item["scenario_id"] == scenario_id:
                return Scenario.model_validate(item)
        raise KeyError(f"Unknown scenario: {scenario_id}")

    def create(self, scenario: Scenario) -> Scenario:
        payload = json.loads(self.path.read_text())
        if any(item.get("scenario_id") == scenario.scenario_id for item in payload):
            raise ValueError(f"Scenario already exists: {scenario.scenario_id}")
        payload.append(scenario.model_dump(mode="json"))
        self.path.write_text(json.dumps(payload, indent=2))
        return scenario


@dataclass
class TesterAgent:
    api_url: str = DEFAULT_API_URL
    project_context_repository: ProjectContextRepository = ProjectContextRepository(DEFAULT_PROJECT_CONTEXTS_PATH)
    scenario_repository: ScenarioRepository = ScenarioRepository(DEFAULT_SCENARIOS_PATH)
    borrower_case_service: FileBorrowerCaseService = FileBorrowerCaseService()
    borrower_profile_service: FileBorrowerProfileService = FileBorrowerProfileService()
    temperature: float = 0.2

    def __post_init__(self) -> None:
        self.borrower_llm = build_chat_llm(
            temperature=self.temperature,
            model_env_keys=("OPENAI_TESTER_MODEL", "OPENAI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"),
        )

    def run(
        self,
        borrower_id: str,
        workflow_id: str,
        max_turns: int,
        experiment_id: str | None = None,
        project_context_id: str | None = None,
        scenario_id: str | None = None,
        project_context: ProjectContext | None = None,
        scenario: Scenario | None = None,
        prompt_version_overrides: dict[str, str] | None = None,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> TesterRunResult:
        project_context = project_context or self.project_context_repository.get(project_context_id or "")
        scenario = scenario or self.scenario_repository.get(scenario_id or "")
        experiment_id = experiment_id or workflow_id

        turn_count = 0
        borrower_message = scenario.opening_message
        follow_up_index = 0
        stop_reason = "max_turns_reached"
        conversation_history: list[tuple[str, str]] = []

        while turn_count < max_turns:
            pre_turn_case = self.borrower_case_service.get_borrower_case(borrower_id)
            current_actor = self._current_agent_actor(borrower_id, pre_turn_case)
            # self._log_case_snapshot(
            #     experiment_id=experiment_id,
            #     workflow_id=workflow_id,
            #     actor=f"{current_actor}_case_state_before",
            #     borrower_case=pre_turn_case,
            #     turn_count=turn_count,
            #     borrower_message=borrower_message,
            # )
            logging_service.log(
                borrower_message,
                experiment_id=experiment_id,
                workflow_id=workflow_id,
                actor="borrower",
            )
            self._emit_event(
                event_callback,
                actor="borrower",
                message=borrower_message,
            )
            conversation_history.append(("borrower", borrower_message))
            response = self._post_message(
                borrower_id=borrower_id,
                workflow_id=workflow_id,
                message=borrower_message,
                prompt_version_overrides=prompt_version_overrides,
                simulation_uniqueness_tag=f"{workflow_id}:{turn_count}:{time_ns()}",
            )
            if response.reply:
                logging_service.log(
                    response.reply,
                    experiment_id=experiment_id,
                    workflow_id=None,
                    actor=current_actor,
                )
                self._emit_event(
                    event_callback,
                    actor=current_actor,
                    message=response.reply,
                )
                conversation_history.append((current_actor, response.reply))
            post_turn_case = self.borrower_case_service.get_borrower_case(borrower_id)
            # self._log_case_snapshot(
            #     experiment_id=experiment_id,
            #     workflow_id=workflow_id,
            #     actor=f"{current_actor}_case_state_after",
            #     borrower_case=post_turn_case,
            #     turn_count=turn_count,
            #     borrower_message=borrower_message,
            #     agent_reply=response.reply,
            # )
            self._log_handoff_events(
                experiment_id=experiment_id,
                workflow_id=workflow_id,
                pre_turn_case=pre_turn_case,
                post_turn_case=post_turn_case,
            )
            turn_count += 1

            if response.final_result:
                stop_reason = "system_ended_conversation"
                break
            if self._system_clearly_ended(response.reply):
                stop_reason = "system_clearly_ended_conversation"
                break

            decision = self._build_next_message(
                borrower_id=borrower_id,
                project_context=project_context,
                scenario=scenario,
                conversation_history=conversation_history,
                system_reply=response.reply,
                follow_up_index=follow_up_index,
            )
            borrower_message = self._normalize_borrower_message(
                decision.message.strip(),
                conversation_history=conversation_history,
                follow_up_index=follow_up_index,
            )
            if not borrower_message:
                stop_reason = "scenario_goal_reached"
                break
            follow_up_index += 1

        return TesterRunResult(
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            borrower_id=borrower_id,
            scenario_id=scenario.scenario_id,
            turn_count=turn_count,
            stop_reason=stop_reason,
        )

    def _emit_event(
        self,
        callback: Callable[[dict[str, Any]], None] | None,
        *,
        actor: str,
        message: str,
    ) -> None:
        if callback is None:
            return
        callback(
            {
                "actor": actor,
                "message": message,
            }
        )

    def _build_next_message(
        self,
        borrower_id: str,
        project_context: ProjectContext,
        scenario: Scenario,
        conversation_history: list[tuple[str, str]],
        system_reply: str | None,
        follow_up_index: int,
    ) -> BorrowerTurnDecision:
        actual_borrower_profile = self.borrower_profile_service.get_borrower_profile(
            scenario.borrower_id or borrower_id
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are the borrower simulator for a debt-collections test harness. "
                        "Generate only the next borrower turn from the scenario persona and intent. "
                        "Do not roleplay as the lender. "
                        "If the scenario objective is achieved or the stop condition is met, set continue_conversation to false. "
                        "Keep borrower behavior realistic and proportional. Do not jump immediately to the strongest refusal, "
                        "verification refusal, or stop-contact style language unless the scenario explicitly supports that behavior. "
                        "Escalate naturally: ask for clarification first, then show skepticism or reluctance, and only then refuse or set contact limits if the conversation justifies it. "
                        "You are speaking as the real borrower, not as a simulator. Never use meta language about profiles, records, prompts, scenarios, test harnesses, or what data you do or do not 'have on hand'. "
                        "Be organic: avoid script-like repetition and avoid reusing near-identical sentence shapes across consecutive turns unless the scenario explicitly requires hard repetition pressure."
                    ),
                ),
                ("human", "{input_prompt}"),
            ]
        )
        chain = prompt | self.borrower_llm.with_structured_output(BorrowerTurnDecision)
        scenario_description = scenario.scenario_description or (
            f"{scenario.borrower_profile} Intent: {scenario.borrower_intent}. "
            f"{scenario.expected_path_notes or ''}"
        ).strip()
        history_text = self._format_history(conversation_history)
        try:
            return chain.invoke(
                {
                    "input_prompt": (
                        f"Project context:\n{project_context.system_under_test}\n\n"
                        f"Testing instructions:\n{json.dumps(project_context.testing_instructions, indent=2)}\n\n"
                        f"Global guardrails:\n{json.dumps(project_context.global_guardrails, indent=2)}\n\n"
                        f"Scenario id: {scenario.scenario_id}\n"
                        f"Scenario description:\n{scenario_description}\n\n"
                        f"Borrower profile:\n{scenario.borrower_profile}\n\n"
                        f"Attached actual borrower profile for the borrower you are simulating:\n"
                        f"{json.dumps(actual_borrower_profile.model_dump(mode='json') if actual_borrower_profile else {'found': False, 'borrower_id': scenario.borrower_id or borrower_id}, indent=2)}\n\n"
                        f"Borrower intent:\n{scenario.borrower_intent}\n\n"
                        f"Reply style rules:\n{json.dumps(scenario.reply_style_rules, indent=2)}\n\n"
                        f"Stop condition:\n{scenario.stop_condition}\n\n"
                        f"Conversation so far:\n{history_text}\n\n"
                        f"Latest system reply:\n{system_reply or ''}\n\n"
                        f"Turn nonce: {follow_up_index}-{time_ns()}\n\n"
                        "If the system asks the borrower to identify themselves, you may use the attached actual borrower profile consistently. "
                        "Do not claim facts that are not present in the attached borrower profile. "
                        "Answer as the borrower would answer naturally if willing. "
                        "If the system asks for identity details that are available in the attached borrower profile, provide the minimum requested identity detail unless the scenario explicitly calls for verification resistance or the conversation has already justified reluctance. "
                        "Never say things like 'I do not have a profile on hand', 'I cannot access my record', or any other meta/system-aware phrasing.\n\n"
                        "Do not repeat the exact same borrower line as the previous borrower turn. "
                        "If the system keeps repeating itself, first try one concise forward-moving response that asks for the next concrete step, then escalate only if repetition continues. "
                        "Prefer cooperative progress when possible: if the system asks a reasonable verification or routing question and scenario rules allow it, answer it directly. "
                        "If the system repeats a question already answered, briefly remind the answer once and ask for the next concrete step instead of parroting the same refusal line. "
                        "Do not use phrases like 'I won't verify', 'don't contact me again', or equivalent hard-boundary language unless the scenario explicitly calls for that behavior or the conversation has already justified that escalation.\n\n"
                        "Return JSON with field:\n"
                        "- message: string\n"
                        "Keep the borrower message concise and consistent with persona."
                    )
                }
            )
        except Exception:
            # Backward-compatible fallback if dynamic generation fails.
            if follow_up_index < len(scenario.follow_up_messages):
                return BorrowerTurnDecision(message=scenario.follow_up_messages[follow_up_index])
            return BorrowerTurnDecision(message="")

    def _format_history(self, conversation_history: list[tuple[str, str]]) -> str:
        if not conversation_history:
            return "(empty)"
        return "\n".join(f"{actor}: {message}" for actor, message in conversation_history)

    def _normalize_borrower_message(
        self,
        message: str,
        conversation_history: list[tuple[str, str]],
        follow_up_index: int,
    ) -> str:
        if not message:
            return message
        last_borrower = ""
        for actor, text in reversed(conversation_history):
            if actor == "borrower":
                last_borrower = text
                break
        if self._normalize_text(message) != self._normalize_text(last_borrower):
            return message
        return self._duplicate_safe_variant(last_borrower, follow_up_index)

    def _duplicate_safe_variant(self, last_borrower: str, follow_up_index: int) -> str:
        normalized = self._normalize_text(last_borrower)
        if any(token in normalized for token in ("cannot pay", "can't pay", "no income", "not commit")):
            variants = [
                "I already shared that I cannot pay right now. Please note that and tell me the next concrete step.",
                "My position is unchanged: no payment capacity right now. Please proceed with the appropriate review path.",
                "I cannot commit to a payment at this time. Confirm the exact next step you can take.",
            ]
            return variants[follow_up_index % len(variants)]
        if any(token in normalized for token in ("closure amount", "settlement", "deadline", "terms")):
            variants = [
                "Understood. I still need the exact amount and deadline so I can decide.",
                "Please share the concrete option details in writing so I can confirm.",
                "I can decide quickly once the exact terms and date are clear.",
            ]
            return variants[follow_up_index % len(variants)]
        variants = [
            "Understood. Please continue with the next concrete step.",
            "Noted. What is the exact next step from here?",
            "I already shared my position. Please proceed with the appropriate next action.",
        ]
        return variants[follow_up_index % len(variants)]

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.lower().split())

    def _post_message(
        self,
        borrower_id: str,
        workflow_id: str,
        message: str,
        prompt_version_overrides: dict[str, str] | None = None,
        simulation_uniqueness_tag: str | None = None,
    ) -> WorkflowMessageResponse:
        payload = json.dumps(
            {
                "borrower_id": borrower_id,
                "workflow_id": workflow_id,
                "message": message,
                "resolution_mode": "CHAT",
                "prompt_version_overrides": prompt_version_overrides or {},
                "simulation_uniqueness_tag": simulation_uniqueness_tag,
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

    def _current_agent_actor(self, borrower_id: str, borrower_case: BorrowerCase | None = None) -> str:
        borrower_case = borrower_case or self.borrower_case_service.get_borrower_case(borrower_id)
        if borrower_case is None:
            return "unknown_agent"
        if borrower_case.stage == Stage.ASSESSMENT:
            return "agent_1"
        if borrower_case.stage == Stage.RESOLUTION:
            return "agent_2"
        if borrower_case.stage == Stage.FINAL_NOTICE:
            return "agent_3"
        return "unknown_agent"

    def _log_handoff_events(
        self,
        experiment_id: str,
        workflow_id: str,
        pre_turn_case: BorrowerCase | None,
        post_turn_case: BorrowerCase | None,
    ) -> None:
        if pre_turn_case is None or post_turn_case is None:
            return
        if pre_turn_case.stage == post_turn_case.stage:
            return
        if not post_turn_case.latest_handoff_summary:
            return

        source_actor = self._current_agent_actor(pre_turn_case.borrower_id, pre_turn_case)
        handoff_payload = {
            "from_stage": pre_turn_case.stage.value,
            "to_stage": post_turn_case.stage.value,
            "summary": post_turn_case.latest_handoff_summary,
        }
        logging_service.log(
            "Handoff",
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            actor=f"{source_actor}_handoff",
            structured_payload=handoff_payload,
        )
        case_state_payload = {
            "from_stage": pre_turn_case.stage.value,
            "to_stage": post_turn_case.stage.value,
            "borrower_case_state": post_turn_case.model_dump(mode="json"),
        }
        logging_service.log(
            "State update",
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            actor=f"{source_actor}_case_state",
            structured_payload=case_state_payload,
        )

    def _log_case_snapshot(
        self,
        experiment_id: str,
        workflow_id: str,
        actor: str,
        borrower_case: BorrowerCase | None,
        turn_count: int,
        borrower_message: str,
        agent_reply: str | None = None,
    ) -> None:
        if borrower_case is None:
            return

        payload = {
            "turn": turn_count + 1,
            "borrower_message": borrower_message,
            "agent_reply": agent_reply,
            "borrower_case_state": borrower_case.model_dump(mode="json"),
        }
        logging_service.log(
            "Case snapshot",
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            actor=actor,
            structured_payload=payload,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one tester scenario against the workflow API")
    parser.add_argument("--project-context-id", required=True)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--borrower-id", required=True)
    parser.add_argument("--workflow-id", required=True)
    parser.add_argument("--experiment-id")
    parser.add_argument("--max-turns", type=int, default=5)
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    args = parser.parse_args()

    agent = TesterAgent(api_url=args.api_url)
    result = agent.run(
        project_context_id=args.project_context_id,
        scenario_id=args.scenario_id,
        borrower_id=args.borrower_id,
        workflow_id=args.workflow_id,
        experiment_id=args.experiment_id,
        max_turns=args.max_turns,
    )
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
logging_service = TranscriptLoggingService()
