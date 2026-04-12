from pydantic import BaseModel


class LenderPolicy(BaseModel):
    lender_id: str
    policy: str
