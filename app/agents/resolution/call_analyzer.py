from __future__ import annotations

import json
import os

from evals.prompt_management_service.prompt_storage import (
    json_prompt_storage_service,
)
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agents.structured_output import parse_agent_turn_result
from app.agents.resolution.tools import build_resolution_tools
from app.domain.borrower_case import AgentTurnResult, BorrowerCase
from app.services.compliance import FileComplianceService


class ResolutionCallAnalyzer:
    def __init__(
        self,
        lender_id: str | None = None,
        prompt_version_id: str | None = None,
        model: str | None = None,
    ) -> None:
        self.lender_id = lender_id or os.getenv("LENDER_ID", "")
        if not self.lender_id:
            raise ValueError("LENDER_ID must be set in env or passed to ResolutionCallAnalyzer")

        self.prompt_version_id = prompt_version_id
        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.tools = build_resolution_tools(self.lender_id)
        self.executor = self._build_executor()

    def _build_executor(self) -> AgentExecutor:
        prompt = (
            json_prompt_storage_service.get_prompt_version("agent_2", self.prompt_version_id)
            if self.prompt_version_id
            else json_prompt_storage_service.get_active_prompt("agent_2")
        )
        prompt_text = prompt.prompt_text
        compliance_rules = FileComplianceService().get_rules_text()
        system_prompt = self._compose_system_prompt(prompt_text, compliance_rules)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=False)

    def _compose_system_prompt(self, prompt_text: str, compliance_rules: str) -> str:
        if not compliance_rules:
            return prompt_text
        return f"{compliance_rules.strip()}\n\nAgent-specific instructions:\n{prompt_text}"

    def analyze_completed_call(
        self,
        borrower_id: str,
        borrower_case: BorrowerCase,
        transcript: str,
    ) -> AgentTurnResult:
        analyzer_input = (
            f"Borrower ID: {borrower_id}\n"
            f"Configured lender ID: {self.lender_id}\n"
            f"Current borrower case context JSON: {json.dumps(borrower_case.to_agent_context(), ensure_ascii=True)}\n"
            "Operational instruction:\n"
            "Analyze this completed Retell voice call transcript for the resolution stage. "
            "The live call is over, so do not continue the conversation. "
            "Return DEAL_AGREED only if the borrower clearly accepted a specific payment or settlement commitment. "
            "Otherwise return NO_DEAL. Do not return CONTINUE. "
            "If you return NO_DEAL, latest_handoff_summary must let Agent 3 continue naturally without restarting.\n\n"
            f"Completed call transcript:\n{transcript}"
        )
        response = self.executor.invoke({"input": analyzer_input})
        return parse_agent_turn_result(response["output"])
