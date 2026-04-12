from pydantic import BaseModel, Field


class Loan(BaseModel):
    account_id: str
    borrower_id: str
    lender_id: str
    amount_due: int = Field(ge=0)
