from datetime import datetime

from pydantic import BaseModel


class ChatMessage(BaseModel):
    message: str
    user_id: str
    workflow_id: str
    agent_id: str
    sender_type: str
    visible_to_borrower: bool = True
    created_at: datetime
