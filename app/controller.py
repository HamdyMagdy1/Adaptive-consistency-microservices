"""Pure-python controller: forest inference without sklearn (fast, no event-loop blocking)."""
import json

FEATURES = ["since_write_ms", "wdecay", "lag_obs_ms", "rate_rps"]

class Controller:
    def __init__(self):
        self.m = None

    def load(self, path, op="1"):
        self.m = json.load(open(path))
        o = self.m["ops"][str(op)]            # operating point = target residual inconsistency (%)
        self.thr, self.thr_crit, self.h, self.h_crit = o["thr"], o["thr_crit"], o["h"], o["h_crit"]
        return {"trees": len(self.m["trees"]), "op": op, **o}

    def prob(self, x):
        s = 0.0
        for t in self.m["trees"]:
            L, R, F, T = t["l"], t["r"], t["f"], t["t"]
            n = 0
            while L[n] != -1:
                n = L[n] if x[F[n]] <= T[n] else R[n]
            s += t["p"][n]
        return s / len(self.m["trees"])

    def decide(self, mode, x, crit):
        """Returns (path, p). A = random forest + cost threshold; H = simple recency rule."""
        m = self.m
        if mode == "A":
            p = self.prob(x)
            thr = self.thr_crit if crit else self.thr
            return ("S" if p >= thr else "E"), p
        T = self.h_crit if crit else self.h
        return ("S" if x[0] < T else "E"), -1.0
