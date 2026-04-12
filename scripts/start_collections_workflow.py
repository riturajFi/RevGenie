from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from temporalio.client import Client

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.temporal.models import CollectionsWorkflowInput
from app.temporal.workflows import BorrowerCollectionsWorkflow


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python3 scripts/start_collections_workflow.py <borrower_id> <workflow_id>")

    borrower_id = sys.argv[1]
    workflow_id = sys.argv[2]
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    handle = await client.start_workflow(
        BorrowerCollectionsWorkflow.run,
        CollectionsWorkflowInput(
            borrower_id=borrower_id,
            workflow_id=workflow_id,
        ),
        id=workflow_id,
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue"),
    )
    print(handle.id)


if __name__ == "__main__":
    asyncio.run(main())
