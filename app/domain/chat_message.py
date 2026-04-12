from datetime import datetime

from pydantic import BaseModel


class ChatMessage(BaseModel):
    user_id: str
    chat_message: str
    created_at: datetime
