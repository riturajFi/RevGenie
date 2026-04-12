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

from app.temporal.activities import (
    load_borrower_case,
    run_assessment_turn,
    run_final_notice_turn,
    run_resolution_turn,
    save_borrower_case,
)
from app.temporal.workflows import BorrowerCollectionsWorkflow


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
            ],
            activity_executor=activity_executor,
        )
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
