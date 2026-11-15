"""Projector: consumes update events and applies them to the Redis read model after a (controllable) lag."""
import asyncio, json, time
import redis.asyncio as aioredis
from aiokafka import AIOKafkaConsumer
from . import config as C

LUA = """
local cur = redis.call('HGET', KEYS[1], 'v')
if (not cur) or tonumber(cur) < tonumber(ARGV[1]) then
  redis.call('HSET', KEYS[1], 'v', ARGV[1], 's', ARGV[2]); return 1
end
return 0
"""

async def main():
    r = aioredis.from_url(C.REDIS_URL, decode_responses=True)
    apply_ = r.register_script(LUA)
    c = AIOKafkaConsumer(C.TOPIC, bootstrap_servers=C.KAFKA, group_id="projector",
                         auto_offset_reset="earliest", enable_auto_commit=True)
    await c.start()
    lag_ms, last = C.LAG_MS, 0.0
    ew, lastpub = None, 0.0

    async def publish(val):
        nonlocal lastpub
        t = time.time()
        if t - lastpub > 0.2:
            await r.set("obs:lag_ms", f"{val:.1f}"); lastpub = t
    try:
        async for m in c:
            e = json.loads(m.value)
            now = time.time()
            if now - last > 0.2:                       # refresh controls a few times per second
                v = await r.get("ctl:lag_ms"); lag_ms = float(v) if v else C.LAG_MS; last = now
            while await r.get("ctl:pause") == "1":     # fault injection: projector paused
                await publish((time.time() - e["ts"]) * 1000)   # age of the held event = observable lag
                await asyncio.sleep(0.05)
            due = e["ts"] + lag_ms / 1000.0
            wait = due - time.time()
            if wait > 0:
                await asyncio.sleep(wait)
            await apply_(keys=[f"i:{e['i']}"], args=[e["v"], e["s"]])
            obs = (time.time() - e["ts"]) * 1000
            ew = obs if ew is None else 0.9 * ew + 0.1 * obs
            await publish(ew)
    finally:
        await c.stop(); await r.aclose()

if __name__ == "__main__":
    asyncio.run(main())
