from fastapi import FastAPI

from app.api.assessment_agent import router as assessment_agent_router
from app.api.borrower_case import router as borrower_case_router
from app.api.borrower_profile import router as borrower_profile_router
from app.api.final_notice_agent import router as final_notice_agent_router
from app.api.lender_policy import router as lender_policy_router
from app.api.lender_profile import router as lender_profile_router
from app.api.loan import router as loan_router
from app.api.resolution_agent import router as resolution_agent_router

app = FastAPI(title="RevGenie")
app.include_router(assessment_agent_router)
app.include_router(final_notice_agent_router)
app.include_router(resolution_agent_router)
app.include_router(borrower_case_router)
app.include_router(borrower_profile_router)
app.include_router(lender_policy_router)
app.include_router(lender_profile_router)
app.include_router(loan_router)
