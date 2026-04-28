import asyncio
import time
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        t0 = time.time()
        r = await client.get("https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-04-28")
        print(f"Schedule: {time.time() - t0:.2f}s")
        data = r.json()
        games = data.get("dates", [])[0].get("games", []) if data.get("dates") else []
        print(f"Found {len(games)} games")
        
        async def fetch(pk):
            t1 = time.time()
            try: await client.get(f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live")
            except: pass
            print(f"Game {pk} live: {time.time() - t1:.2f}s")
            
        t2 = time.time()
        await asyncio.gather(*(fetch(g["gamePk"]) for g in games[:5]))
        print(f"Gather 5 games: {time.time() - t2:.2f}s")

asyncio.run(main())
