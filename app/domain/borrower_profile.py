from pydantic import BaseModel, ConfigDict


class BorrowerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    borrower_id: str
    full_name: str
    phone_number: str
