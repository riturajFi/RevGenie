from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys
from pathlib import Path

from temporalio.client import Client
from temporalio.worker import Worker

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from env_loader import load_env_file

load_env_file()

from app.orchestrator.activities import (
    finalize_resolution_call,
    load_borrower_case,
    run_assessment_turn,
    run_final_notice_turn,
    run_resolution_turn,
    save_borrower_case,
    start_final_notice_stage,
    start_resolution_call,
)
from app.orchestrator.workflows import BorrowerCollectionsWorkflow


async def main() -> None:
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[BorrowerCollectionsWorkflow],
            activities=[
                load_borrower_case,
                save_borrower_case,
                run_assessment_turn,
                run_resolution_turn,
                run_final_notice_turn,
                start_resolution_call,
                finalize_resolution_call,
                start_final_notice_stage,
            ],
            activity_executor=activity_executor,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
