"""E-046 — Ch2 LARGE: global epoch-aware re-route on the FINE tof grid.

E-572 (coarse 0.1d grid) found a cheap-cost global order ~389d that was
UNWALKABLE (epoch-shift trap) and its feasible walks plateaued ~1000d.
E-045 proved the 0.1d grid over-states tof ~0.12 d/leg. This re-runs the
SAME global epoch-aware OR-Tools re-route but with the cost matrix AND
the chronological walk on the 0.005d grid, to scope whether the grid fix
makes the global reorder approach r1=424.62 (the pole) — a single
decisive probe before committing multi-day effort.

Imports E-572 as a module (keeps its worker fns picklable for mp.Pool),
overrides only the grids / iteration budget / output. Writes best
feasible candidate to /tmp ONLY; never touches solutions/upload.
"""
import importlib.util
import os
import sys

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

# Fine grid for the COST matrix — must be set before importing E-572
# (its N_STEPS / TOF_WINDOW are read at module import time).
# window 12 / 1200 steps = 0.01d resolution (E-045's working fine grid).
os.environ["E572_NSTEPS"] = os.environ.get("E584_NSTEPS", "1200")
os.environ["E572_TOFWIN"] = "12.0"
os.environ["E572_WORKERS"] = os.environ.get("E584_WORKERS", "4")

spec = importlib.util.spec_from_file_location(
    "e572mod", f"{ROOT}/scripts/ch2_e572_large_global_epoch_lkh.py")
e572 = importlib.util.module_from_spec(spec)
sys.modules["e572mod"] = e572          # register so mp workers can unpickle
spec.loader.exec_module(e572)

# Override the WALK grid to fine. Keep the WIDE window=40 (the greedy
# walker needs it to reproduce the bank topology; a narrow 12d window
# strands legs needing tof>12d), refine resolution: 40/4000 = 0.01d.
e572.WALK = dict(tof_window=40.0, n_steps=4000, wait_steps=8, wait_dt=1.0)
e572.N_ITERS = int(os.environ.get("E584_ITERS", "4"))
e572.TL = int(os.environ.get("E584_TL", "900"))
e572.STOP_DELTA = float(os.environ.get("E584_STOP", "3.0"))
e572.OUT = "/tmp/ch2_large_global_finegrid_cand.json"
e572.CURRENT_BANK = 1013.2886

if __name__ == "__main__":
    print(f"[E-584] global epoch-aware FINE-grid probe: cost n_steps="
          f"{e572.N_STEPS} walk n_steps={e572.WALK['n_steps']} "
          f"iters={e572.N_ITERS} TL={e572.TL}s vs bank {e572.CURRENT_BANK}",
          flush=True)
    e572.main()
