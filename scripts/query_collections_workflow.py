from __future__ import annotations

import asyncio
import json
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
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 scripts/query_collections_workflow.py <workflow_id>")

    workflow_id = sys.argv[1]
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    handle = client.get_workflow_handle(workflow_id)
    state = await handle.query(BorrowerCollectionsWorkflow.get_state)
    if state is None:
        print("null")
        return
    print(json.dumps(state.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
