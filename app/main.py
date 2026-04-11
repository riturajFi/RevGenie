from fastapi import FastAPI

from app.api.borrower_case import router as borrower_case_router
from app.api.borrower_profile import router as borrower_profile_router
from app.api.lender_profile import router as lender_profile_router
from app.api.loan import router as loan_router

app = FastAPI(title="RevGenie")
app.include_router(borrower_case_router)
app.include_router(borrower_profile_router)
app.include_router(lender_profile_router)
app.include_router(loan_router)
