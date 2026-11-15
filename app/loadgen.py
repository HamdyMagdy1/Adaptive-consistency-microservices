"""Open-loop load generator with Zipf item popularity. Logs one row per request."""
import argparse, asyncio, json, time, os
import aiohttp, numpy as np
import redis.asyncio as aioredis
from . import config as C

async def lag_schedule(rds, t_start, sched, events):
    for t, lag in sched:
        d = t_start + t - time.time()
        if d > 0: await asyncio.sleep(d)
        await rds.set("ctl:lag_ms", str(lag)); events.append((round(time.time(), 3), lag))

async def pause_schedule(rds, t_start, pauses, events):
    for start, dur in pauses:
        d = t_start + start - time.time()
        if d > 0: await asyncio.sleep(d)
        await rds.set("ctl:pause", "1"); events.append((round(time.time(), 3), "pause_on"))
        await asyncio.sleep(dur)
        await rds.set("ctl:pause", "0"); events.append((round(time.time(), 3), "pause_off"))

async def main(a):
    sched = [(float(x.split(":")[0]), float(x.split(":")[1])) for x in a.lag_schedule.split(",")]
    rds = aioredis.from_url(C.REDIS_URL, decode_responses=True)
    events = []
    pauses = [(float(x.split(":")[0]), float(x.split(":")[1])) for x in a.pause.split(",")] if a.pause else []
    rng = np.random.default_rng(a.seed)
    p = 1.0 / np.arange(1, a.items + 1) ** a.zipf; p /= p.sum()
    n = int(a.rate * a.duration)
    gaps = rng.exponential(1.0 / a.rate, n)
    items = rng.choice(np.arange(1, a.items + 1), n, p=p)
    is_w = rng.random(n) < a.write_frac
    crit = (rng.random(n) < a.crit_frac) & ~is_w
    rows = []
    conn = aiohttp.TCPConnector(limit=a.conns)
    async with aiohttp.ClientSession(connector=conn) as s:
        if a.mode in ("A", "H"):
            async with s.post(f"{C.GATEWAY}/controller/reload", params={"op": a.op}) as r: await r.read()
        await s.post(f"{C.GATEWAY}/run/start", params={"run_id": a.run_id})
        t_start = time.time()
        sched_task = asyncio.create_task(lag_schedule(rds, t_start, sched, events))
        pause_task = asyncio.create_task(pause_schedule(rds, t_start, pauses, events))
        async def one(i, tsend):
            p0 = time.perf_counter()
            try:
                if is_w[i]:
                    async with s.post(f"{C.GATEWAY}/write/{items[i]}", params={"delta": -1}) as r:
                        await r.read(); st = r.status
                else:
                    async with s.get(f"{C.GATEWAY}/read/{items[i]}", params={"mode": a.mode, "crit": int(crit[i])}) as r:
                        await r.read(); st = r.status
            except Exception:
                st = 0
            rows.append((tsend, "w" if is_w[i] else "r", int(items[i]), int(crit[i]), a.mode, (time.perf_counter() - p0) * 1000, st))
        tasks = []; nxt = time.perf_counter()
        for i in range(n):
            nxt += gaps[i]
            d = nxt - time.perf_counter()
            if d > 0: await asyncio.sleep(d)
            tasks.append(asyncio.create_task(one(i, time.time())))
        await asyncio.gather(*tasks)
        await s.post(f"{C.GATEWAY}/run/stop")
        sched_task.cancel(); pause_task.cancel()
        await rds.set("ctl:pause", "0"); await rds.set("ctl:lag_ms", str(C.LAG_MS)); await rds.aclose()
    os.makedirs(C.LOGDIR, exist_ok=True)
    with open(f"{C.LOGDIR}/{a.run_id}_client.csv", "w") as f:
        f.write("ts,op,item,crit,mode,lat_ms,status\n")
        for r in rows: f.write(",".join(map(str, r)) + "\n")
    json.dump(dict(start=t_start, warmup=a.warmup, rate=a.rate, mode=a.mode, duration=a.duration, lag_events=events, lag_schedule=a.lag_schedule, op=a.op, pause=a.pause),
              open(f"{C.LOGDIR}/{a.run_id}_meta.json", "w"))
    print("done", a.run_id, len(rows), "requests")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="E"); ap.add_argument("--rate", type=float, default=300)
    ap.add_argument("--duration", type=float, default=40); ap.add_argument("--warmup", type=float, default=10)
    ap.add_argument("--write-frac", type=float, default=0.2); ap.add_argument("--crit-frac", type=float, default=0.3)
    ap.add_argument("--items", type=int, default=100000); ap.add_argument("--zipf", type=float, default=1.1)
    ap.add_argument("--conns", type=int, default=200); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lag-schedule", default="0:20"); ap.add_argument("--op", default="1"); ap.add_argument("--pause", default=""); ap.add_argument("--run-id", required=True)
    asyncio.run(main(ap.parse_args()))
