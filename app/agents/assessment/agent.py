from __future__ import annotations

import os

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.agents.assessment.tools import build_assessment_tools
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
                        "Keep responses concise, factual, and direct."
                    ),
                ),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=False)

    def invoke(self, borrower_id: str, message: str, chat_history: list[ChatMessage] | None = None) -> dict:
        agent_input = (
            f"Borrower ID: {borrower_id}\n"
            f"Configured lender ID: {self.lender_id}\n"
            f"Borrower message: {message}"
        )
        response = self.executor.invoke(
            {
                "input": agent_input,
                "chat_history": self._to_langchain_messages(chat_history or []),
            }
        )
        return {"reply": response["output"]}

    def _to_langchain_messages(self, chat_history: list[ChatMessage]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for item in chat_history:
            if item.user_id.startswith("agent:"):
                messages.append(AIMessage(content=item.chat_message))
            else:
                messages.append(HumanMessage(content=item.chat_message))
        return messages
