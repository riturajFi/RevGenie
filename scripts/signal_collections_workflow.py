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
from app.orchestrator.workflows import BorrowerCollectionsWorkflow

load_env_file()


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python3 scripts/signal_collections_workflow.py <workflow_id> <message>")

    workflow_id = sys.argv[1]
    message = " ".join(sys.argv[2:])
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    handle = client.get_workflow_handle(workflow_id)
    await handle.execute_update(BorrowerCollectionsWorkflow.handle_borrower_message, message)
    print("update_sent")


if __name__ == "__main__":
    asyncio.run(main())
