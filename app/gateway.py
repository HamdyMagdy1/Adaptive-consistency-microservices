"""Gateway: executes reads (E/V/S + controller modes A/H) and writes; logs features and outcomes."""
import asyncio, json, math, time, os
from contextlib import asynccontextmanager
import asyncpg, redis.asyncio as aioredis
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, HTTPException
from . import config as C
from .controller import Controller

S = {"run": None, "reads": [], "writes": []}
FEAT = {"lw": {}, "wd": {}, "lag": 0.0, "bucket": int(time.time()), "cnt": 0, "rate": 0.0}
TAU = 5.0
CTL = Controller()

def note_req():
    b = int(time.time())
    if b != FEAT["bucket"]:
        FEAT["rate"] = FEAT["cnt"] / max(b - FEAT["bucket"], 1)
        FEAT["cnt"] = 0; FEAT["bucket"] = b
    FEAT["cnt"] += 1

async def lag_refresher():
    while True:
        try:
            v = await S["r"].get("obs:lag_ms")
            FEAT["lag"] = float(v) if v else 0.0
        except Exception:
            pass
        await asyncio.sleep(0.2)

@asynccontextmanager
async def lifespan(app):
    S["pg"] = await asyncpg.create_pool(C.PG_DSN, min_size=5, max_size=30)
    S["r"] = aioredis.from_url(C.REDIS_URL, decode_responses=True)
    S["k"] = AIOKafkaProducer(bootstrap_servers=C.KAFKA, linger_ms=5)
    await S["k"].start()
    task = asyncio.create_task(lag_refresher())
    if os.path.exists(C.MODEL):
        CTL.load(C.MODEL)
    yield
    task.cancel()
    await S["k"].stop(); await S["pg"].close(); await S["r"].aclose()

app = FastAPI(lifespan=lifespan)

async def _redis_version(item):
    v = await S["r"].hget(f"i:{item}", "v")
    return int(v) if v is not None else 0

@app.get("/health")
async def health():
    return {"ok": True, "controller_loaded": CTL.m is not None}

@app.post("/controller/reload")
async def reload_ctl(path: str = "", op: str = "1"):
    return CTL.load(path or C.MODEL, op)

@app.get("/read/{item}")
async def read(item: int, mode: str = "E", crit: int = 0):
    t0 = time.time(); p0 = time.perf_counter()
    note_req()
    lw = FEAT["lw"].get(item)
    since = min((t0 - lw) * 1000.0, 600000.0) if lw else 600000.0
    wd = FEAT["wd"].get(item, 0.0) * math.exp(-(t0 - lw) / TAU) if lw else 0.0
    x = [since, wd, FEAT["lag"], FEAT["rate"]]
    path, p = mode, -1.0
    if mode in ("A", "H"):
        if CTL.m is None:
            raise HTTPException(503, "controller model not loaded")
        path, p = CTL.decide(mode, x, crit)
    if path == "E":                      # eventual: read model only
        v = await _redis_version(item)
    elif path == "S":                    # strong: authoritative store
        v = await S["pg"].fetchval("SELECT version FROM items WHERE id=$1", item)
    else:                                # validated: read model, then version check at the source
        v = await _redis_version(item)
        pv = await S["pg"].fetchval("SELECT version FROM items WHERE id=$1", item)
        if pv > v:
            v = pv
    lat = (time.perf_counter() - p0) * 1000
    if S["run"]:
        logged = mode if mode in ("E", "V", "S") else f"{mode}_{path}"
        S["reads"].append((t0, item, crit, logged, v, lat, round(since, 1), round(wd, 3),
                           round(FEAT["lag"], 1), round(FEAT["rate"], 1), round(p, 4)))
    return {"item": item, "version": v, "mode": path}

@app.post("/write/{item}")
async def write(item: int, delta: int = -1):
    note_req()
    row = await S["pg"].fetchrow(
        "UPDATE items SET stock=stock+$2, version=version+1 WHERE id=$1 RETURNING version, stock", item, delta)
    ts = time.time()                      # recorded right after commit
    prev = FEAT["lw"].get(item)
    FEAT["wd"][item] = (FEAT["wd"].get(item, 0.0) * math.exp(-max(ts - prev, 0.0) / TAU) if prev else 0.0) + 1.0
    FEAT["lw"][item] = ts
    await S["k"].send(C.TOPIC, key=str(item).encode(),
                      value=json.dumps({"i": item, "v": row["version"], "s": row["stock"], "ts": ts}).encode())
    if S["run"]:
        S["writes"].append((ts, item, row["version"]))
    return {"item": item, "version": row["version"]}

@app.post("/run/start")
async def run_start(run_id: str):
    S["run"] = run_id; S["reads"] = []; S["writes"] = []
    return {"started": run_id}

@app.post("/run/stop")
async def run_stop():
    rid = S["run"]; S["run"] = None
    os.makedirs(C.LOGDIR, exist_ok=True)
    with open(f"{C.LOGDIR}/{rid}_reads.csv", "w") as f:
        f.write("ts,item,crit,mode,v,lat_ms,since_write_ms,wdecay,lag_obs_ms,rate_rps,p\n")
        for r in S["reads"]: f.write(",".join(map(str, r)) + "\n")
    with open(f"{C.LOGDIR}/{rid}_writes.csv", "w") as f:
        f.write("ts,item,v\n")
        for w in S["writes"]: f.write(",".join(map(str, w)) + "\n")
    return {"stopped": rid, "reads": len(S["reads"]), "writes": len(S["writes"])}
