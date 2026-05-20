"""Ch2 KTTSP — fcmaes coordinated-retry global optimizer.

User insight (S-2026-05-20): leaderboard submission helper is named
`fcmaes` — strongly suggests rank-1/3 used Dietmar Wolz's fcmaes
library. fcmaes is purpose-built for the GTOC/SpOC-style problems
(orbital trajectory + mixed continuous/integer).

Encoding for Ch2 (145-dim decision vector):
  x[0:48]     = departure times (continuous, [0, 200])
  x[48:96]    = times of flight (continuous, [0.001, 200])
  x[96:145]   = real-valued permutation keys ([0, 1]); decode via
                argsort to get the tomato permutation 0..48.

Objective: makespan = times[-1] + tofs[-1] if feasible; else a
penalty proportional to feasibility violation magnitude.

Optimisation: `retry.minimize(de_cma)` runs N parallel CMA-ES runs
with restarts, picking the best feasible. de_cma is DE for global
exploration + CMA-ES for local exploitation — Wolz's standard
recipe for this problem class.

Optional warm-start: encode the banked 142.99d perm as initial
guess for one (or more) population members.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np
from fcmaes import cmaes
from scipy.optimize import Bounds

from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP

# Loaded by mp.Pool initializer — fcmaes copies state across workers
_WORKER_KT = [None]


def _init_problem(inst):
    """Load KTTSP once per worker process."""
    _WORKER_KT[0] = KTTSP(inst)


def _decode(x, n=49):
    """Decode flat real vector → (times, tofs, perm)."""
    times = x[:n - 1]
    tofs = x[n - 1:2 * (n - 1)]
    perm_keys = x[2 * (n - 1):2 * (n - 1) + n]
    perm = np.argsort(perm_keys).tolist()
    return times, tofs, perm


def _fitness(x, kt):
    """fcmaes-style objective: makespan if feasible, else penalty."""
    n = kt.n
    times, tofs, perm = _decode(x, n)
    # Build the official decision vector
    x_off = list(times) + list(tofs) + [float(p) for p in perm]
    f = kt.fitness(x_off)
    if kt.is_feasible(f):
        return float(f[0])   # the makespan
    # Penalty: sum of violation magnitudes scaled by big-M
    pen = 1000.0 + 1e3 * (max(0, f[1])
                          + max(0, -f[2]) * 10
                          + max(0, -f[3]) * 10
                          + max(0, f[4]) * 50)
    # plus makespan contribution
    return float(pen + f[0])


class _Ch2Problem:
    """fcmaes-style problem wrapper with bounds + obj."""

    def __init__(self, inst):
        self.inst = inst
        self._kt = None
        kt = KTTSP(inst)
        self.kt = kt
        self.n = kt.n
        # bounds
        lo_times = [0.0] * (kt.n - 1)
        hi_times = [kt.max_time] * (kt.n - 1)
        lo_tofs = [kt.min_tof + 1e-4] * (kt.n - 1)
        hi_tofs = [kt.max_time] * (kt.n - 1)
        lo_perm = [0.0] * kt.n
        hi_perm = [1.0] * kt.n
        self.lo = np.array(lo_times + lo_tofs + lo_perm)
        self.hi = np.array(hi_times + hi_tofs + hi_perm)
        self.bounds = Bounds(self.lo, self.hi)
        self.dim = len(self.lo)

    def fitness(self, x):
        # fcmaes calls this per-evaluation, possibly across processes
        if self._kt is None:
            self._kt = KTTSP(self.inst)
        return _fitness(x, self._kt)

    # fcmaes expects a __call__ for the fitness function
    def __call__(self, x):
        return self.fitness(x)


def encode_solution(kt, decision_vector):
    """Encode an official decision vector (times+tofs+perm) into
    fcmaes-style flat real vector (with permutation-as-real-keys)."""
    n = kt.n
    times = decision_vector[:n - 1]
    tofs = decision_vector[n - 1:2 * (n - 1)]
    perm = [round(v) for v in decision_vector[2 * (n - 1):]]
    # Real keys: perm[k] = position-in-sorted-order
    # If we set perm_keys[perm[k]] = k/(n-1), argsort gives back perm
    keys = np.zeros(n)
    for pos, node in enumerate(perm):
        keys[node] = pos / max(1, n - 1)
    return np.concatenate([times, tofs, keys])


class _BestTracker:
    """Wrap a fitness function to keep best-ever-seen across all evals."""
    def __init__(self, fn):
        self.fn = fn
        self.best_fun = float("inf")
        self.best_x = None

    def __call__(self, x):
        v = self.fn(x)
        if v < self.best_fun:
            self.best_fun = float(v)
            self.best_x = np.array(x, copy=True)
        return v


def _single_cma(args):
    """Single CMA-ES run from a given x0 with perturbation sigma.
    Tracks best-ever-seen (CMA-ES returns final μ which may have
    drifted into infeasible territory)."""
    inst, x0, sigma, max_evals, seed = args
    p = _Ch2Problem(inst)
    rng = np.random.default_rng(seed)
    x_init = np.clip(x0 + rng.normal(0, sigma, size=len(x0)), p.lo, p.hi)
    tracker = _BestTracker(p.fitness)
    # Always record the warm-start itself
    tracker(x0)
    tracker(x_init)
    try:
        cmaes.minimize(
            tracker, bounds=p.bounds, x0=x_init,
            input_sigma=sigma, max_evaluations=max_evals,
            popsize=24, stop_fitness=1.0)
    except Exception as e:
        return seed, tracker.best_fun, tracker.best_x, str(e)
    return seed, tracker.best_fun, tracker.best_x, None


def run(inst, problem="small",
        warm_start_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
        max_evals=50_000, n_workers=4, n_retries=32,
        out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
        seed=0):
    kt = KTTSP(inst)
    p = _Ch2Problem(inst)
    print(f"Problem: n={kt.n}, dim={p.dim}, bounds shape={p.lo.shape}",
          flush=True)

    # Encode warm-start (mandatory for this run)
    if warm_start_path is None:
        print("No warm-start: aborting (search from random rarely "
              "finds feasibility on this landscape)", flush=True)
        return {"problem": problem, "feasible": False,
                "note": "no warm-start"}
    with open(warm_start_path) as fh:
        data = json.load(fh)
    decision_v = data[0]["decisionVector"]
    x0_enc = encode_solution(kt, decision_v)
    fmk = p.fitness(x0_enc)
    print(f"Warm-start: encoded mk={fmk:.3f} (expect 142.989)",
          flush=True)

    # Build args for parallel CMA-ES runs with varying perturbation
    # sigma — small for refinement, larger for exploration.
    sigmas = []
    for k in range(n_retries):
        # First 1/3: small sigma (refinement)
        # Middle 1/3: medium sigma (basin transitions)
        # Last 1/3: large sigma (escape current basin)
        if k < n_retries // 3:
            sigmas.append(0.02)
        elif k < 2 * n_retries // 3:
            sigmas.append(0.10)
        else:
            sigmas.append(0.30)
    args = [(inst, x0_enc, sig, max_evals, k + 1000 * seed)
            for k, sig in enumerate(sigmas)]
    print(f"Launching {n_retries} parallel CMA-ES runs "
          f"(sigmas: {sigmas[0]}, {sigmas[n_retries//3]}, "
          f"{sigmas[2*n_retries//3]}), max_evals={max_evals}, "
          f"workers={n_workers}", flush=True)
    t0 = time.time()
    results = []
    with mp.Pool(n_workers, initializer=_init_problem,
                 initargs=(inst,)) as pool:
        for sd, fun, x_best, err in pool.imap_unordered(
                _single_cma, args):
            if err is not None:
                print(f"  seed={sd}: ERR {err}", flush=True)
                continue
            results.append((fun, x_best, sd))
            print(f"  seed={sd}: fun={fun:.3f}", flush=True)
    wall = time.time() - t0
    print(f"All {n_retries} runs done: wall={wall:.1f}s", flush=True)
    if not results:
        return {"problem": problem, "feasible": False,
                "wall_s": round(wall, 1), "all_errored": True}
    results.sort(key=lambda r: r[0])
    best_fun, best_x, best_seed = results[0]
    print(f"BEST: fun={best_fun:.3f} (seed={best_seed})", flush=True)
    result = type("R", (), {"fun": best_fun, "x": best_x})()

    info = {"problem": problem, "n": kt.n, "wall_s": round(wall, 1),
            "max_evals": max_evals, "n_workers": n_workers,
            "n_retries": n_retries, "n_finished": len(results),
            "rank3_small_d": 111.76,
            "best_fitness": float(result.fun)}

    # Decode best
    times, tofs, perm = _decode(result.x, kt.n)
    decision_v = list(times) + list(tofs) + [float(v) for v in perm]
    f = kt.fitness(decision_v)
    feas = kt.is_feasible(f)
    info["fitness"] = list(f)
    info["feasible"] = feas
    info["perm"] = perm
    if feas and f[0] < 142.99:
        p_path = Path(out) / f"{problem}.json"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        p_path.write_text(json.dumps([{"decisionVector": list(decision_v),
                                       "problem": problem,
                                       "challenge": CHALLENGE}]))
        info["banked_artifact"] = str(p_path)
        info["banked_mk"] = float(f[0])
    return info


if __name__ == "__main__":
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    me = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
    nw = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    nr = int(sys.argv[3]) if len(sys.argv) > 3 else 32
    print(json.dumps(run(inst, max_evals=me, n_workers=nw,
                         n_retries=nr), indent=2))
