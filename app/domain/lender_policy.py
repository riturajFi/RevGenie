from pydantic import BaseModel, ConfigDict


class LenderPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lender_id: str
    policy: str
