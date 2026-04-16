import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from env_loader import load_env_file
from app.api.borrower_auth import router as borrower_auth_router
from app.api.borrower_case import router as borrower_case_router
from app.api.borrower_profile import router as borrower_profile_router
from app.api.evals import router as evals_router
from app.api.lender_policy import router as lender_policy_router
from app.api.lender_profile import router as lender_profile_router
from app.api.loan import router as loan_router
from app.api.workflows import router as workflows_router

load_env_file()

app = FastAPI(title="RevGenie")
allowed_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(borrower_auth_router)
app.include_router(borrower_case_router)
app.include_router(borrower_profile_router)
app.include_router(lender_policy_router)
app.include_router(lender_profile_router)
app.include_router(loan_router)
app.include_router(workflows_router)
app.include_router(evals_router)
