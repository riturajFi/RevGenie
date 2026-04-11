from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    chat_message: str
    created_at: datetime
