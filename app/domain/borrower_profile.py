from pydantic import BaseModel


class BorrowerProfile(BaseModel):
    borrower_id: str
    full_name: str
    phone_number: str
