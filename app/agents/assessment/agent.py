from __future__ import annotations

import json
import os

from evals.prompt_management_service.prompt_storage import (
    json_prompt_storage_service,
)
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.structured_output import parse_agent_turn_result
from app.agents.assessment.tools import build_assessment_tools
from app.domain.borrower_case import AgentTurnResult, BorrowerCase
from app.domain.chat_message import ChatMessage
from app.services.compliance import FileComplianceService
from app.services.llm_factory import build_chat_llm


class AssessmentAgent:
    def __init__(
        self,
        lender_id: str | None = None,
        prompt_version_id: str | None = None,
        model: str | None = None,
    ) -> None:
        self.lender_id = lender_id or os.getenv("LENDER_ID", "")
        if not self.lender_id:
            raise ValueError("LENDER_ID must be set in env or passed to AssessmentAgent")

        self.prompt_version_id = prompt_version_id
        self.llm = build_chat_llm(
            model=model,
            temperature=0,
            model_env_keys=("OPENAI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"),
        )
        self.tools = build_assessment_tools(self.lender_id)
        self.executor = self._build_executor()

    def _build_executor(self) -> AgentExecutor:
        prompt = (
            json_prompt_storage_service.get_prompt_version("agent_1", self.prompt_version_id)
            if self.prompt_version_id
            else json_prompt_storage_service.get_active_prompt("agent_1")
        )
        prompt_text = prompt.prompt_text
        compliance_rules = FileComplianceService().get_rules_text()
        system_prompt = self._compose_system_prompt(prompt_text, compliance_rules)
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=system_prompt),
                MessagesPlaceholder("chat_history", optional=True),
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

    def invoke(
        self,
        borrower_id: str,
        message: str,
        borrower_case: BorrowerCase,
        chat_history: list[ChatMessage] | None = None,
    ) -> AgentTurnResult:
        return self._invoke(borrower_id, message, borrower_case, chat_history or [], None)

    def invoke_with_instruction(
        self,
        borrower_id: str,
        borrower_case: BorrowerCase,
        instruction: str,
        message: str | None = None,
        chat_history: list[ChatMessage] | None = None,
    ) -> AgentTurnResult:
        return self._invoke(borrower_id, message or "", borrower_case, chat_history or [], instruction)

    def _invoke(
        self,
        borrower_id: str,
        message: str,
        borrower_case: BorrowerCase,
        chat_history: list[ChatMessage],
        instruction: str | None,
    ) -> AgentTurnResult:
        agent_input = (
            f"Borrower ID: {borrower_id}\n"
            f"Configured lender ID: {self.lender_id}\n"
            f"Current borrower case context JSON: {json.dumps(borrower_case.to_agent_context(), ensure_ascii=True)}\n"
            f"Operational instruction: {instruction or 'Handle the current borrower turn.'}\n"
            f"Borrower message: {message}"
        )
        response = self.executor.invoke(
            {
                "input": agent_input,
                "chat_history": self._to_langchain_messages(chat_history),
            }
        )
        return parse_agent_turn_result(response["output"])

    def _to_langchain_messages(self, chat_history: list[ChatMessage]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for item in chat_history:
            if item.sender_type == "system":
                # Anthropic requires the system instruction to be first and singular.
                # Treat stage system notes as conversational context instead.
                messages.append(HumanMessage(content=f"[System context] {item.message}"))
            elif item.sender_type == "agent":
                messages.append(AIMessage(content=item.message))
            else:
                messages.append(HumanMessage(content=item.message))
        return messages
