from pydantic import BaseModel, ConfigDict


class LenderProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lender_id: str
    lender_name: str
