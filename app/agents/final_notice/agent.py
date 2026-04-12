from __future__ import annotations

import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agents.structured_output import parse_agent_turn_result
from app.agents.final_notice.tools import build_final_notice_tools
from app.domain.borrower_case import AgentTurnResult, BorrowerCase


class FinalNoticeAgent:
    def __init__(self, lender_id: str | None = None, model: str | None = None) -> None:
        self.lender_id = lender_id or os.getenv("LENDER_ID", "")
        if not self.lender_id:
            raise ValueError("LENDER_ID must be set in env or passed to FinalNoticeAgent")

        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.tools = build_final_notice_tools(self.lender_id)
        self.executor = self._build_executor()

    def _build_executor(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are Agent 3, the Final Notice agent for a debt collections workflow. "
                        "You are consequence-driven, deadline-focused, and leave zero ambiguity. "
                        "You must identify yourself as an AI agent acting on behalf of the lender and disclose that the conversation is being logged. "
                        "You do not argue. You do not persuade. You do not sympathize. "
                        "You state facts, state the final available option if one exists, state the hard expiry, and state what happens next. "
                        "The consequences may include credit reporting, legal referral, asset recovery, or account escalation, but you must not fabricate any consequence. "
                        "Only state consequences that are consistent with the provided handoff context, case details, and lender policy. "
                        "You will receive a summary from Agent 2 that contains the voice-stage outcome, including offers made, objections raised, and the borrower's position. "
                        "Treat that summary as the handoff context instead of relying on prior chat history. "
                        "Use tools to fetch borrower information, borrower case, lender-scoped loan information, lender information, and lender policy. "
                        "Never invent account details, policy terms, deadlines, or next steps. "
                        "Keep replies concise, explicit, and final. "
                        "Your final answer must be valid JSON only with this shape: "
                        "{\"reply\": str, \"stage_outcome\": \"CONTINUE\"|\"RESOLVED\"|\"NO_RESOLUTION\", "
                        "\"case_delta\": {}, "
                        "\"latest_handoff_summary\": str|null}. "
                        "Return only changed BorrowerCase fields in case_delta using dotted field paths mapped to their changed values."
                    ),
                ),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=False)

    def invoke(
        self,
        borrower_id: str,
        resolution_summary: str,
        message: str,
        borrower_case: BorrowerCase,
    ) -> AgentTurnResult:
        return self._invoke(borrower_id, resolution_summary, message, borrower_case, None)

    def invoke_with_instruction(
        self,
        borrower_id: str,
        resolution_summary: str,
        borrower_case: BorrowerCase,
        instruction: str,
        message: str | None = None,
    ) -> AgentTurnResult:
        return self._invoke(borrower_id, resolution_summary, message or "", borrower_case, instruction)

    def _invoke(
        self,
        borrower_id: str,
        resolution_summary: str,
        message: str,
        borrower_case: BorrowerCase,
        instruction: str | None,
    ) -> AgentTurnResult:
        agent_input = (
            f"Borrower ID: {borrower_id}\n"
            f"Configured lender ID: {self.lender_id}\n"
            f"Current borrower case JSON: {borrower_case.model_dump_json()}\n"
            f"Resolution handoff summary from Agent 2:\n{resolution_summary}\n\n"
            f"Operational instruction:\n{instruction or 'Handle the current borrower turn.'}\n\n"
            f"Latest borrower message:\n{message}"
        )
        response = self.executor.invoke({"input": agent_input})
        return parse_agent_turn_result(response["output"])
