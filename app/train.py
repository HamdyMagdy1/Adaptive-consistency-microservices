"""Train the Random Forest on E-mode logs; tune thresholds on held-out validation RUNS; export model.json."""
import argparse, json
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from . import config as C
from .analyze import labeled
from .controller import FEATURES

COL = {"since_write_ms": "since_write_ms", "wdecay": "wdecay", "lag_obs_ms": "lag_obs_ms", "rate_rps": "rate_rps"}

def load(runs):
    ds = []
    for r in runs:
        _, m, _ = labeled(r, warm=5); m["run"] = r; ds.append(m)
    return pd.concat(ds, ignore_index=True)

def pick_thr(p, stale, target):
    """Largest threshold whose residual inconsistency (stale reads not sent to S) is <= target %."""
    best = 0.0
    for t in np.unique(np.round(p, 4)):
        if 100 * ((p < t) & stale).mean() <= target: best = max(best, t)
    return float(best)

def pick_since(since, stale, target):
    """Smallest recency window T (send to S if since<T) whose residual inconsistency is <= target %."""
    for T in [0, 5, 10, 20, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000, 30000, 600001]:
        if 100 * ((since >= T) & stale).mean() <= target: return float(T)
    return 600001.0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--val", required=True)
    a = ap.parse_args()
    tr, va = load(a.train.split(",")), load(a.val.split(","))
    X, y = tr[FEATURES].values, tr.stale.values.astype(int)
    clf = RandomForestClassifier(n_estimators=40, max_depth=8, min_samples_leaf=100, n_jobs=1, random_state=0).fit(X, y)
    pv = clf.predict_proba(va[FEATURES].values)[:, 1]; yv = va.stale.values
    print(f"train reads={len(tr)} stale={100*y.mean():.2f}% | val reads={len(va)} stale={100*yv.mean():.2f}%")
    print(f"VAL  AUC={roc_auc_score(yv, pv):.3f}  AP={average_precision_score(yv, pv):.3f}  Brier={brier_score_loss(yv, pv):.4f}")
    print("feature importance:", dict(zip(FEATURES, clf.feature_importances_.round(3))))
    crit = va.crit.values == 1
    since = va.since_write_ms.values
    def rep(name, sel):                       # sel = boolean array "send to S"
        print(f"  {name:22s} S-share={100*sel.mean():5.1f}%   residual inconsistency={100*((~sel)&yv).mean():.2f}%")
    ops = {}
    print("policies on validation runs (residual inconsistency target; crit target = half):")
    rep("always E", np.zeros(len(yv), bool)); rep("always S", np.ones(len(yv), bool))
    for tg in [0.5, 1.0, 2.0, 5.0, 10.0]:
        thr = pick_thr(pv, yv, tg); thr_c = pick_thr(pv[crit], yv[crit], tg / 2)
        hT = pick_since(since, yv, tg); hTc = pick_since(since[crit], yv[crit], tg / 2)
        ops[str(int(tg)) if tg == int(tg) else str(tg)] = dict(thr=thr, thr_crit=thr_c, h=hT, h_crit=hTc)
        rep(f"A  target {tg}%", np.where(crit, pv >= thr_c, pv >= thr))
        rep(f"H  target {tg}%", np.where(crit, since < hTc, since < hT))
    trees = []
    for e in clf.estimators_:
        t = e.tree_; v = t.value[:, 0, :]
        trees.append(dict(l=t.children_left.tolist(), r=t.children_right.tolist(), f=t.feature.tolist(),
                          t=t.threshold.tolist(), p=(v[:, 1] / v.sum(axis=1)).tolist()))
    json.dump(dict(features=FEATURES, ops=ops, trees=trees), open(f"{C.LOGDIR}/model.json", "w"))
    print("saved model.json; operating points:", {k: {a: round(b, 4) for a, b in v.items()} for k, v in ops.items()})
