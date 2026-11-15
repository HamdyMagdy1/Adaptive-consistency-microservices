"""Ground truth: a read is inconsistent if it returned an older version than the latest one committed before the read started."""
import json, sys, os
import numpy as np, pandas as pd
from . import config as C

def labeled(run, warm=None):
    meta = json.load(open(f"{C.LOGDIR}/{run}_meta.json"))
    rd = pd.read_csv(f"{C.LOGDIR}/{run}_reads.csv"); wr = pd.read_csv(f"{C.LOGDIR}/{run}_writes.csv")
    t0 = meta["start"] + (meta["warmup"] if warm is None else warm)
    wr = wr.sort_values(["item", "ts"]); wr["lv"] = wr.groupby("item")["v"].cummax()
    wr = wr.sort_values("ts")
    m = pd.merge_asof(rd.sort_values("ts"), wr[["ts", "item", "lv"]], on="ts", by="item", direction="backward")
    m["lv"] = m["lv"].fillna(0)
    m = m[m.ts >= t0].copy()
    m["stale"] = m["v"] < m["lv"]; m["behind"] = (m["lv"] - m["v"]).clip(lower=0)
    return meta, m, t0

def analyze(run):
    meta, m, t0 = labeled(run)
    cl = pd.read_csv(f"{C.LOGDIR}/{run}_client.csv")
    c = cl[(cl.ts >= t0)]; cr = c[c.op == "r"]; ok = c[c.status == 200]
    win = max(c.ts.max() - t0, 1e-9)
    return dict(run=run, mode=meta["mode"], rate=meta["rate"], reads=len(m),
                incons_pct=100 * m.stale.mean(),
                incons_crit_pct=100 * m[m.crit == 1].stale.mean() if (m.crit == 1).any() else 0.0,
                mean_versions_behind=m.behind.mean(),
                s_share_pct=100 * m["mode"].astype(str).str.endswith("S").mean(),
                p50_ms=cr.lat_ms.quantile(.50), p95_ms=cr.lat_ms.quantile(.95), p99_ms=cr.lat_ms.quantile(.99),
                throughput_rps=len(ok) / win, errors=int((c.status != 200).sum()))

if __name__ == "__main__":
    out = pd.DataFrame([analyze(r) for r in sys.argv[1:]]).round(3)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(out.to_string(index=False)); out.to_csv(f"{C.LOGDIR}/{os.getenv('OUT', 'summary')}.csv", index=False)
