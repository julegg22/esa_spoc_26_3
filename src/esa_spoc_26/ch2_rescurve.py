"""Ch2 Q3 — resolution→cheap-edge-density curve.

The recurring root cause (E-017): every router is only as good as its
edge graph, and cheapness keeps rising with search resolution
(coarse 74 → local 89 → 1.5-d-global 138 → hi-accuracy ?). This
experiment measures, on a FIXED sample of ordered pairs, how the
#≤100 / #≤600 cheap-edge count and median Δv improve as a function of
edge-search compute — so we know the *marginal value* of heavier
edge compute and where the curve flattens (the heavy-compute target).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from esa_spoc_26.ch2_kttsp import _WORKER_KT, KTTSP, _init_worker

# resolution ladder: (label, t_dep_step_d, tof_max_d, n_refine_seeds, maxiter)
LADDER = [
    ("coarse", 3.0, 30.0, 3, 40),
    ("medium", 1.5, 50.0, 6, 80),
    ("fine", 1.0, 80.0, 12, 150),
    ("veryfine", 0.5, 110.0, 20, 250),
]


def _samp_worker(args):
    inst, i, j, tstep, tofmax, nseed, maxit, max_time, min_tof = args
    kt = _WORKER_KT[0] if _WORKER_KT else KTTSP(inst)
    tg = np.arange(0.0, max_time - 0.5, tstep)
    fg = np.concatenate([np.arange(0.2, 6, 0.25), np.arange(6, tofmax, 2.5)])
    cands = []
    for td in tg:
        for tf in fg:
            if td + tf > max_time:
                continue
            cands.append((kt.compute_transfer(i, j, float(td), float(tf)),
                          float(td), float(tf)))
    cands.sort(key=lambda c: c[0])
    best = cands[0][0]
    seen = []
    for _d, td0, tf0 in cands:
        if any(abs(td0 - s) < 3.0 for s in seen):
            continue
        seen.append(td0)
        if len(seen) > nseed:
            break
        try:
            r = minimize(
                lambda p: kt.compute_transfer(
                    i, j, max(p[0], 0.0),
                    min(max(p[1], min_tof), max_time - max(p[0], 0.0))),
                np.array([td0, tf0]), method="Nelder-Mead",
                options={"xatol": 1e-4, "fatol": 1e-3, "maxiter": maxit})
            best = min(best, float(r.fun))
        except Exception:
            pass
    return best


def run(inst, n_sample=180, n_workers=4, seed=0):
    import multiprocessing as mp

    kt = KTTSP(inst)
    n = kt.n
    rng = np.random.default_rng(seed)
    pairs = set()
    while len(pairs) < n_sample:
        a, b = int(rng.integers(n)), int(rng.integers(n))
        if a != b:
            pairs.add((a, b))
    pairs = sorted(pairs)
    out = []
    for label, ts, tm, nseed, maxit in LADDER:
        args = [(inst, a, b, ts, tm, nseed, maxit, kt.max_time, kt.min_tof)
                for a, b in pairs]
        t0 = time.time()
        with mp.Pool(n_workers, initializer=_init_worker,
                     initargs=(inst,)) as pool:
            dv = np.array(pool.map(_samp_worker, args))
        out.append({
            "res": label, "t_step": ts, "tof_max": tm, "seeds": nseed,
            "wall_s": round(time.time() - t0, 1),
            "frac_le100": round(float((dv <= 100).mean()), 4),
            "frac_le600": round(float((dv <= 600).mean()), 4),
            "median_dv": round(float(np.median(dv)), 1),
            "min_dv": round(float(dv.min()), 1)})
        print(json.dumps(out[-1]), flush=True)
    # plot density vs cumulative compute
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cum = np.cumsum([o["wall_s"] for o in out])
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.plot(cum, [o["frac_le100"] * 100 for o in out], "o-",
                label="% pairs ≤100 m/s")
        ax.plot(cum, [o["frac_le600"] * 100 for o in out], "s--",
                label="% pairs ≤600 m/s")
        for o, c in zip(out, cum, strict=True):
            ax.annotate(o["res"], (c, o["frac_le100"] * 100), fontsize=8)
        ax.set_xlabel(
            f"cumulative edge-search compute (s, {n_sample}-pair sample)")
        ax.set_ylabel("% of sampled pairs feasible")
        ax.set_title("Ch2: marginal value of edge-search compute")
        ax.legend(fontsize=8)
        fig.tight_layout()
        d = Path("/home/julian/Projects/esa_spoc_26_3/vault/experiments/"
                 "E-019")
        d.mkdir(parents=True, exist_ok=True)
        fig.savefig(d / "rescurve.png", dpi=110)
    except Exception as e:
        print("plot skipped:", e)
    return out


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    print(json.dumps({"summary": run(inst, n_sample=ns)}, indent=2))
