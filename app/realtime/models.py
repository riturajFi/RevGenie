from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.borrower_case import BorrowerCase


class BorrowerConversationMessage(BaseModel):
    id: str
    actor: Literal["borrower", "agent", "system"]
    text: str
    created_at: datetime


class BorrowerConversationState(BaseModel):
    borrower_case: BorrowerCase
    workflow_id: str
    final_result: str | None = None
    input_enabled: bool
    messages: list[BorrowerConversationMessage]


class BorrowerSocketClientMessage(BaseModel):
    type: Literal["borrower_message"]
    message: str


class BorrowerSocketServerEvent(BaseModel):
    type: Literal["conversation_state", "error"]
    state: BorrowerConversationState | None = None
    message: str | None = None
