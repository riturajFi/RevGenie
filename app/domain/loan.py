from pydantic import BaseModel, ConfigDict, Field


class Loan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    borrower_id: str
    lender_id: str
    amount_due: int = Field(ge=0)
