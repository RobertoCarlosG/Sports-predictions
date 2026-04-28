import sys
import os
sys.path.insert(0, os.path.abspath('src'))
import asyncio
import time
import httpx
from app.services.mlb_client import MlbApiClient

async def main():
    async with httpx.AsyncClient() as http_client:
        client = MlbApiClient("https://statsapi.mlb.com/api/v1", http_client)
        t0 = time.time()
        raw = await client.schedule("2026-04-28")
        games = raw.get("dates", [])[0].get("games", []) if raw.get("dates") else []
        
        async def fetch(pk):
            try: await client.boxscore(pk)
            except: pass
            try: await client.live_feed(pk)
            except: pass
            try: await client.linescore(pk)
            except: pass
            
        await asyncio.gather(*(fetch(g["gamePk"]) for g in games))
        print(f"All {len(games)} games took: {time.time() - t0:.2f}s")

asyncio.run(main())
