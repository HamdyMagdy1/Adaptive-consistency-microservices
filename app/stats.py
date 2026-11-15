"""Aggregate repetitions: mean/sd, bootstrap 95% CI, paired Wilcoxon (exact) with Holm correction.
Usage: python -m app.stats summary_a.csv [summary_b.csv ...]   (run ids look like ev_A1_s3)"""
import re, sys, os
import numpy as np, pandas as pd
from scipy.stats import wilcoxon
from . import config as C

# Pre-specified primary hypotheses (A at the 5% operating point is lower than its comparator) in every scenario.
PRIMARY = {("A5 vs H5", "s_share_pct"), ("A5 vs H5", "incons_pct"), ("A5 vs S", "p95_ms"), ("A5 vs E", "incons_pct")}
METRICS = ["incons_pct", "incons_crit_pct", "s_share_pct", "p50_ms", "p95_ms", "p99_ms"]

def boot_ci(x, n=5000, seed=0):
    x = np.asarray(x, float)
    if len(x) < 2: return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x)), replace=True).mean(axis=1)
    return tuple(np.percentile(m, [2.5, 97.5]))

def holm(ps):
    order = np.argsort(ps); adj = np.empty(len(ps)); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (len(ps) - rank) * ps[i]); adj[i] = min(run, 1.0)
    return adj

if __name__ == "__main__":
    df = pd.concat([pd.read_csv(p) for p in sys.argv[1:]], ignore_index=True).drop_duplicates("run")
    ex = df.run.str.extract(r"^(?:(ev|S\d+))_([A-Z]\d*)_s(\d+)$")
    df["scen"], df["policy"], df["seed"] = ex[0].replace("ev", "S1"), ex[1], ex[2].astype(float)
    df = df.dropna(subset=["policy"]); df["seed"] = df.seed.astype(int)
    order = ["E", "S", "V", "H1", "H5", "A1", "A5"]
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 40)
    pairs = [("A1", "H1", "s_share_pct"), ("A1", "H1", "incons_pct"), ("A5", "H5", "s_share_pct"), ("A5", "H5", "incons_pct"),
             ("A1", "S", "p95_ms"), ("A1", "S", "p99_ms"), ("A5", "S", "p95_ms"), ("A5", "S", "p99_ms"),
             ("A1", "E", "incons_pct"), ("A5", "E", "incons_pct"), ("A1", "H1", "p95_ms"), ("A5", "H5", "p95_ms"),
             ("A1", "V", "p95_ms"), ("A1", "V", "p99_ms")]
    res = []
    for sc, d0 in df.groupby("scen"):
        rows = []
        for pol, g in d0.groupby("policy"):
            r = {"policy": pol, "n": len(g)}
            for k in METRICS:
                lo, hi = boot_ci(g[k])
                r[k] = f"{g[k].mean():.2f} ± {g[k].std(ddof=1) if len(g) > 1 else float('nan'):.2f} [{lo:.2f},{hi:.2f}]"
            rows.append(r)
        tab = pd.DataFrame(rows).set_index("policy").reindex([p for p in order if p in set(d0.policy)])
        print(f"\n=== scenario {sc}: mean ± sd [bootstrap 95% CI of the mean]\n", tab.to_string())
        tab.to_csv(f"{C.LOGDIR}/stats_table_{sc}.csv")
        for a_, b_, k in pairs:
            pa = d0[d0.policy == a_].set_index("seed")[k]; pb = d0[d0.policy == b_].set_index("seed")[k]
            sd = pa.index.intersection(pb.index)
            if len(sd) < 3: continue
            d = pa[sd] - pb[sd]
            p = wilcoxon(pa[sd], pb[sd]).pvalue if (d != 0).any() else 1.0
            res.append(dict(scenario=sc, test=f"{a_} vs {b_}", metric=k, n=len(sd), mean_diff=round(d.mean(), 3), p=p))
    if res:
        r = pd.DataFrame(res)
        prim = r.apply(lambda x: (x.test, x.metric) in PRIMARY, axis=1)
        r["family"] = np.where(prim, "primary", "exploratory")
        r["p_holm"] = np.nan
        for fam in ["primary", "exploratory"]:      # Holm within each pre-specified family
            m = r.family == fam
            if m.any(): r.loc[m, "p_holm"] = holm(r.loc[m, "p"].values)
        r["p_holm"] = r.p_holm.round(4); r["p"] = r.p.round(4)
        print("\npaired Wilcoxon (two-sided, exact). Holm applied within each family (primary = pre-specified, exploratory = the rest)\n",
              r.sort_values(["family", "scenario"]).to_string(index=False))
        r.to_csv(f"{C.LOGDIR}/stats_tests.csv", index=False)
        nmin = int(r.n.min())
        if nmin < 6: print(f"\nNOTE: n={nmin} pairs; exact Wilcoxon cannot reach p<0.05 with n<6. Use >=10 repetitions for claims.")
