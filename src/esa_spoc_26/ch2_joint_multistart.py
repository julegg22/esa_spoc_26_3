"""Ch2 KTTSP — multistart joint NLP polish.

SLSQP from banked converged in 8 iters at 142.9183 (0.002d gain).
That's the basin attractor of the current warm start. To escape,
seed SLSQP from JITTERED starts: ±k% perturbation on (td, tof)
followed by a feasibility-projection pre-pass. Best feasible result
wins.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from esa_spoc_26.ch2_joint_nlp_polish import joint_polish
from esa_spoc_26.ch2_kttsp import CHALLENGE, KTTSP


def main(in_path="/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json",
         out="/home/julian/Projects/esa_spoc_26_3/solutions/upload",
         problem="small", n_starts=12, jitter=0.05, seed=0):
    inst = ("reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
            "Salesperson Problem/problems/easy.kttsp")
    kt = KTTSP(inst)
    with open(in_path) as fh:
        data = json.load(fh)
    x0 = data[0]["decisionVector"]
    n = kt.n
    perm = [round(v) for v in x0[2 * n - 2:]]
    initial_mk = kt.fitness(x0)[0]
    print(f"Initial: mk={initial_mk:.4f} d", flush=True)
    times0 = np.array(x0[:n - 1])
    tofs0 = np.array(x0[n - 1:2 * (n - 1)])
    cap_per_leg = []
    safety_margin = 5e-4
    for k in range(n - 1):
        dv0 = kt.compute_transfer(perm[k], perm[k + 1],
                                   float(times0[k]), float(tofs0[k]))
        cap_orig = kt.dv_exc if dv0 > kt.dv_thr else kt.dv_thr
        cap_per_leg.append(cap_orig - safety_margin)
    rng = np.random.default_rng(seed)
    best_mk = float(initial_mk)
    best_x = list(x0)
    t0 = time.time()
    for s in range(n_starts):
        if s == 0:
            t_init = times0.copy()
            tof_init = tofs0.copy()
        else:
            # Jittered start — preserve chronology by sorting after jitter
            t_init = times0 * (1 + rng.uniform(-jitter, jitter,
                                                size=len(times0)))
            tof_init = tofs0 * (1 + rng.uniform(-jitter, jitter,
                                                  size=len(tofs0)))
            # Project to chronological by walking
            for k in range(1, len(t_init)):
                t_ready = t_init[k - 1] + tof_init[k - 1]
                if t_init[k] < t_ready:
                    t_init[k] = t_ready
            # Clamp tof to [min, 40] and total to max_time
            tof_init = np.clip(tof_init, max(kt.min_tof, 0.05), 40.0)
            for k in range(len(t_init)):
                if t_init[k] + tof_init[k] > kt.max_time:
                    tof_init[k] = max(kt.min_tof,
                                       kt.max_time - t_init[k] - 0.01)
        try:
            times, tofs, mk = joint_polish(
                kt, perm, list(t_init), list(tof_init),
                cap_per_leg, maxiter=300, verbose=False)
        except Exception as e:
            print(f"  start {s}: SLSQP error {e}", flush=True)
            continue
        x_new = times + tofs + [float(p) for p in perm]
        f = kt.fitness(x_new)
        feas = kt.is_feasible(f)
        mk_eval = float(f[0])
        marker = ""
        if feas and mk_eval < best_mk - 1e-4:
            best_mk = mk_eval
            best_x = list(x_new)
            marker = "  ✓ NEW BEST"
        elif feas:
            marker = " feas"
        else:
            marker = " INFEAS"
        print(f"  start {s}: mk={mk_eval:.4f}{marker}", flush=True)
    wall = time.time() - t0
    f_best = kt.fitness(best_x)
    info = {"problem": problem, "n": n, "wall_s": round(wall, 1),
            "initial_mk": float(initial_mk),
            "best_mk": float(f_best[0]),
            "feasible": kt.is_feasible(f_best),
            "delta_d": float(initial_mk - f_best[0]),
            "n_starts": n_starts,
            "rank3_small_d": 111.76}
    if kt.is_feasible(f_best) and f_best[0] < initial_mk - 0.001:
        p = Path(out) / f"{problem}.json"
        p.write_text(json.dumps([{"decisionVector": list(best_x),
                                  "problem": problem,
                                  "challenge": CHALLENGE}]))
        info["banked"] = str(p)
    return info


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    js = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    sd = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    print(json.dumps(main(n_starts=ns, jitter=js, seed=sd), indent=2))
