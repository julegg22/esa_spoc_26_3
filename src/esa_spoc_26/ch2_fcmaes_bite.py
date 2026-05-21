"""Ch2 KTTSP — BiteOpt variant of fcmaes (Wolz's first-try recommendation).

Per O-009 fcmaes README + ESAChallenge tutorial: "If your problem is
single objective and if you have no clue what algorithm to apply,
try BiteOpt first." Different exploration dynamics than CMA-ES;
may escape the 142.99 basin where CMA-ES couldn't (E-025).

Same encoding as ch2_fcmaes.py (argsort permutation + continuous td,
tof). BiteOpt + multi-start + best-tracker.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
from fcmaes import bitecpp

from esa_spoc_26.ch2_fcmaes import _BestTracker, _Ch2Problem, _decode, encode_solution
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def _single_bite(args):
    """Single BiteOpt run from a perturbed warm-start."""
    inst, x0, sigma, max_evals, seed = args
    p = _Ch2Problem(inst)
    rng = np.random.default_rng(seed)
    x_init = np.clip(x0 + rng.normal(0, sigma, size=len(x0)), p.lo, p.hi)
    tracker = _BestTracker(p.fitness)
    tracker(x0)
    tracker(x_init)
    try:
        bitecpp.minimize(
            tracker, bounds=p.bounds, x0=x_init,
            max_evaluations=max_evals)
    except Exception as e:
        return seed, tracker.best_fun, tracker.best_x, str(e)
    return seed, tracker.best_fun, tracker.best_x, None


def run(inst, problem="small",
        warm_start_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
        max_evals=50_000, n_workers=4, n_retries=16, seed=0,
        out="/home/julian/Projects/esa_spoc_26_3/solutions/upload"):
    kt = KTTSP(inst)
    p = _Ch2Problem(inst)
    print(f"BiteOpt: n={kt.n}, dim={p.dim}", flush=True)

    if warm_start_path is None:
        return {"problem": problem, "feasible": False,
                "note": "no warm-start"}
    with open(warm_start_path) as fh:
        data = json.load(fh)
    x0_enc = encode_solution(kt, data[0]["decisionVector"])
    print(f"Warm-start: mk={p.fitness(x0_enc):.3f}", flush=True)

    # Multi-start with sigma in [0.005, 0.02, 0.10, 0.30] — broader
    # than CMA-ES (since BiteOpt is more exploration-friendly)
    sigmas = []
    for k in range(n_retries):
        if k < n_retries // 4:
            sigmas.append(0.005)
        elif k < 2 * n_retries // 4:
            sigmas.append(0.02)
        elif k < 3 * n_retries // 4:
            sigmas.append(0.10)
        else:
            sigmas.append(0.30)
    args = [(inst, x0_enc, sig, max_evals, k + 1000 * seed)
            for k, sig in enumerate(sigmas)]
    print(f"Launching {n_retries} BiteOpt runs, max_evals={max_evals}, "
          f"workers={n_workers}", flush=True)
    t0 = time.time()
    results = []
    from esa_spoc_26.ch2_fcmaes import _init_problem
    with mp.Pool(n_workers, initializer=_init_problem,
                 initargs=(inst,)) as pool:
        for sd, fun, x_best, err in pool.imap_unordered(_single_bite,
                                                         args):
            if err is not None:
                print(f"  seed={sd}: ERR {err}", flush=True)
                continue
            results.append((fun, x_best, sd))
            print(f"  seed={sd}: fun={fun:.3f}", flush=True)
    wall = time.time() - t0
    if not results:
        return {"problem": problem, "feasible": False,
                "wall_s": round(wall, 1), "all_errored": True}
    results.sort(key=lambda r: r[0])
    best_fun, best_x, best_seed = results[0]
    info = {"problem": problem, "wall_s": round(wall, 1),
            "max_evals": max_evals, "n_retries": n_retries,
            "best_fitness": float(best_fun), "best_seed": int(best_seed),
            "rank3_small_d": 111.76}
    times, tofs, perm = _decode(best_x, kt.n)
    x_dec = list(times) + list(tofs) + [float(p) for p in perm]
    f = kt.fitness(x_dec)
    feas = kt.is_feasible(f)
    info["fitness"] = list(f)
    info["feasible"] = feas
    if feas and f[0] < 142.99:
        p_path = Path(out) / f"{problem}.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        p_path.write_text(json.dumps([{"decisionVector": list(x_dec),
                                       "problem": problem,
                                       "challenge": CHALLENGE}]))
        info["banked"] = str(p_path)
        info["banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    me = int(sys.argv[1]) if len(sys.argv) > 1 else 30_000
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    nr = int(sys.argv[3]) if len(sys.argv) > 3 else 16
    print(json.dumps(run(inst, max_evals=me, n_workers=nw,
                         n_retries=nr), indent=2))
