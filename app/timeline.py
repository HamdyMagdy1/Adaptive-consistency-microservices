"""Per-10s-window inconsistency and p95 latency for runs, to see behaviour over time."""
import json, sys, os
import numpy as np, pandas as pd
from . import config as C
W = 10

def one(run):
    meta = json.load(open(f"{C.LOGDIR}/{run}_meta.json")); t0 = meta["start"]
    rd = pd.read_csv(f"{C.LOGDIR}/{run}_reads.csv"); wr = pd.read_csv(f"{C.LOGDIR}/{run}_writes.csv")
    cl = pd.read_csv(f"{C.LOGDIR}/{run}_client.csv")
    wr = wr.sort_values(["item", "ts"]); wr["lv"] = wr.groupby("item")["v"].cummax(); wr = wr.sort_values("ts")
    m = pd.merge_asof(rd.sort_values("ts"), wr[["ts", "item", "lv"]], on="ts", by="item", direction="backward")
    m["lv"] = m["lv"].fillna(0); m["stale"] = (m["v"] < m["lv"]) * 100.0
    m["w"] = ((m.ts - t0) // W * W).astype(int)
    cr = cl[cl.op == "r"].copy(); cr["w"] = ((cr.ts - t0) // W * W).astype(int)
    return m.groupby("w").stale.mean().rename(run), cr.groupby("w").lat_ms.quantile(.95).rename(run)

if __name__ == "__main__":
    res = [one(r) for r in sys.argv[1:]]
    inc = pd.concat([a for a, _ in res], axis=1).round(1); p95 = pd.concat([b for _, b in res], axis=1).round(0)
    pd.set_option("display.width", 200)
    print("\n== inconsistency % per 10s window =="); print(inc.to_string())
    print("\n== p95 read latency (ms) per 10s window =="); print(p95.to_string())
    pre = os.getenv("OUT", "timeline"); inc.to_csv(f"{C.LOGDIR}/{pre}_incons.csv"); p95.to_csv(f"{C.LOGDIR}/{pre}_p95.csv")
