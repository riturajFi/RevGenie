from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from temporalio.client import Client

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from env_loader import load_env_file
from app.domain.borrower_case import ResolutionMode
from app.orchestrator.models import CollectionsWorkflowInput
from app.orchestrator.workflows import BorrowerCollectionsWorkflow

load_env_file()


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: python3 scripts/start_collections_workflow.py <borrower_id> <workflow_id> [CHAT|VOICE]"
        )

    borrower_id = sys.argv[1]
    workflow_id = sys.argv[2]
    resolution_mode = ResolutionMode(sys.argv[3].upper()) if len(sys.argv) >= 4 else ResolutionMode.CHAT
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    handle = await client.start_workflow(
        BorrowerCollectionsWorkflow.run,
        CollectionsWorkflowInput(
            borrower_id=borrower_id,
            workflow_id=workflow_id,
            resolution_mode=resolution_mode,
        ),
        id=workflow_id,
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue"),
    )
    print(handle.id)


if __name__ == "__main__":
    asyncio.run(main())
