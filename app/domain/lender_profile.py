from pydantic import BaseModel


class LenderProfile(BaseModel):
    lender_id: str
    lender_name: str
