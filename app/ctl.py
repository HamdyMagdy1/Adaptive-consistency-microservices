"""Fault-injection controls: python -m app.ctl lag 500 | pause on | pause off"""
import asyncio, sys
import redis.asyncio as aioredis
from . import config as C

async def main():
    r = aioredis.from_url(C.REDIS_URL, decode_responses=True)
    cmd, val = sys.argv[1], sys.argv[2]
    if cmd == "lag": await r.set("ctl:lag_ms", val)
    elif cmd == "pause": await r.set("ctl:pause", "1" if val == "on" else "0")
    print("ok", cmd, val); await r.aclose()

asyncio.run(main())
