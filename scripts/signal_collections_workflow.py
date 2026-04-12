from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.temporal.workflows import BorrowerCollectionsWorkflow


async def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python3 scripts/signal_collections_workflow.py <workflow_id> <message>")

    workflow_id = sys.argv[1]
    message = " ".join(sys.argv[2:])
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        data_converter=pydantic_data_converter,
    )
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(BorrowerCollectionsWorkflow.submit_borrower_message, message)
    print("signal_sent")


if __name__ == "__main__":
    asyncio.run(main())
