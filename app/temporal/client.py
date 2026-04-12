from __future__ import annotations

import os

from temporalio.client import Client


async def get_temporal_client() -> Client:
    return await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
