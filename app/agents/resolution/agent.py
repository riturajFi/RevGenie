from __future__ import annotations

import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agents.prompts import RESOLUTION_SYSTEM_PROMPT
from app.agents.structured_output import parse_agent_turn_result
from app.agents.resolution.tools import build_resolution_tools
from app.domain.borrower_case import AgentTurnResult, BorrowerCase
from app.domain.chat_message import ChatMessage


class ResolutionAgent:
    def __init__(self, lender_id: str | None = None, model: str | None = None) -> None:
        self.lender_id = lender_id or os.getenv("LENDER_ID", "")
        if not self.lender_id:
            raise ValueError("LENDER_ID must be set in env or passed to ResolutionAgent")

        model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.tools = build_resolution_tools(self.lender_id)
        self.executor = self._build_executor()

    def _build_executor(self) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    RESOLUTION_SYSTEM_PROMPT,
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
            f"Operational instruction:\n{instruction or 'Handle the current borrower turn.'}\n\n"
            f"Latest borrower message:\n{message}"
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
                messages.append(SystemMessage(content=item.message))
            elif item.sender_type == "agent":
                messages.append(AIMessage(content=item.message))
            else:
                messages.append(HumanMessage(content=item.message))
        return messages
