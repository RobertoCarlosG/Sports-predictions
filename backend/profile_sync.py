import asyncio
import time
import httpx
import sys
import os

sys.path.insert(0, os.path.abspath('src'))
from app.db.session import async_session_factory
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date

async def main():
    async with httpx.AsyncClient() as http_client:
        client = MlbApiClient("https://statsapi.mlb.com", http_client)
        async with async_session_factory() as session:
            t0 = time.time()
            print("Starting sync...")
            await sync_games_for_date(session, client, "2026-04-28", fetch_details=True)
            print(f"Sync took {time.time() - t0:.2f}s")

asyncio.run(main())
