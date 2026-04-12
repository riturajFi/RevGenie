from __future__ import annotations

import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agents.structured_output import parse_agent_turn_result
from app.agents.assessment.tools import build_assessment_tools
from app.domain.borrower_case import AgentTurnResult, BorrowerCase
from app.domain.chat_message import ChatMessage


class AssessmentAgent:
    def __init__(
        self,
        lender_id: str | None = None,
        model: str | None = None,
    ) -> None:
        self.lender_id = lender_id or os.getenv("LENDER_ID", "")
        if not self.lender_id:
            raise ValueError("LENDER_ID must be set in env or passed to AssessmentAgent")

        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.tools = build_assessment_tools(self.lender_id)
        self.executor = self._build_executor()

    def _build_executor(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are Agent 1, the Assessment agent for a debt collections workflow. "
                        "You are cold, clinical, and all business. "
                        "You must identify yourself as an AI agent acting on behalf of the lender and disclose that the conversation is being logged. "
                        "Do not negotiate. Do not sympathize. Do not make settlement offers. "
                        "Your job is to establish the debt, verify identity using partial account information, gather the borrower's financial situation, "
                        "and determine which resolution path is viable. "
                        "Use tools to fetch borrower information, the borrower's loan for the configured lender, and lender information related to that loan. "
                        "Never invent account details. If a record is missing, say so plainly. "
                        "If identity is not verified, ask the borrower to confirm the last four digits of the account reference. "
                        "If hardship or distress is mentioned, gather facts without pressure and note hardship. "
                        "Keep responses concise, factual, and direct. "
                        "Your final answer must be valid JSON only with this shape: "
                        "{\"reply\": str, \"stage_outcome\": \"CONTINUE\"|\"ASSESSMENT_COMPLETE\", "
                        "\"case_delta\": {}, "
                        "\"latest_handoff_summary\": str|null}. "
                        "Return only changed BorrowerCase fields in case_delta using dotted field paths mapped to their changed values. "
                        "Do not update workflow-controlled fields such as workflow_id, lender_id, amount_due, principal_outstanding, dpd, stage, case_status, final_disposition, or last_contact_channel."
                    ),
                ),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=False)

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
            f"Current borrower case JSON: {borrower_case.model_dump_json()}\n"
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
            if item.user_id.startswith("agent:"):
                messages.append(AIMessage(content=item.chat_message))
            else:
                messages.append(HumanMessage(content=item.chat_message))
        return messages
