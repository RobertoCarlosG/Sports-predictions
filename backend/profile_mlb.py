import asyncio
import time
import httpx
import sys
import os

sys.path.insert(0, os.path.abspath('src'))
from app.services.mlb_client import MlbApiClient

async def main():
    async with httpx.AsyncClient() as http_client:
        client = MlbApiClient("https://statsapi.mlb.com/api/v1", http_client)
        t0 = time.time()
        print("Starting...")
        raw = await client.schedule("2026-04-28")
        print(f"Took {time.time() - t0:.2f}s")

asyncio.run(main())
