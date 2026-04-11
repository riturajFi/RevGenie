from fastapi import FastAPI

from app.api.borrower_case import router as borrower_case_router

app = FastAPI(title="RevGenie")
app.include_router(borrower_case_router)
