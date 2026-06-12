"""E-585 — Ch2 LARGE: windowed destroy-repair LNS on the FINE walk grid,
re-seeded from the current 1013.29 bank.

E-578 was the first method to descend from the (old, coarse) large bank,
but it walks on a 0.13d grid (n_steps=300) and hardcodes CURRENT_BANK to
the old 1048.98. Since E-045 banked 1013.29 on a 0.005-0.01d grid, that
coarse walk no longer reproduces the bank. This driver imports E-578 as a
module and overrides ONLY the walk grid (fine) + the bank reference, so the
windowed LNS searches for window reorderings that beat 1013.29 in the SAME
fine-grid evaluation space the bank lives in.

Per the user's NEVER-STOP directive (2026-06-12): keep grinding the banked
solution even at zero expected point gain — competitors optimize too, and
our biggest wins came from unexpected findings in repeated optimization.

GUARDED: best feasible candidate -> /tmp ONLY; banks NOTHING. The loop
guard-banks separately only if a candidate re-scores < 1013.2886 officially.
"""
import importlib.util
import os
import sys

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")

spec = importlib.util.spec_from_file_location(
    "e578mod", f"{ROOT}/scripts/ch2_e578_large_window_lns.py")
e578 = importlib.util.module_from_spec(spec)
sys.modules["e578mod"] = e578
spec.loader.exec_module(e578)

# Fine walk grid (window=40 keeps the greedy walker able to reach legs that
# need tof>12d; n_steps=4000 -> 0.01d resolution, E-584's working fine walk).
e578.WALK = dict(tof_window=40.0, n_steps=int(os.environ.get("E585_NSTEPS", "4000")),
                 wait_steps=8, wait_dt=float(os.environ.get("E585_WAITDT", "0.25")))
e578.CURRENT_BANK = 1013.2886
e578.SEED = int(os.environ.get("E578_SEED", os.environ.get("E585_SEED", "0")))
e578.OUT = os.environ.get("E585_OUT", f"/tmp/ch2_large_window_finegrid_cand_s{e578.SEED}.json")
# Slightly larger windows + a bit more repair time than the coarse default.
e578.WMIN = int(os.environ.get("E585_WMIN", "20"))
e578.WMAX = int(os.environ.get("E585_WMAX", "50"))
e578.SOLVE_S = int(os.environ.get("E585_SOLVES", "6"))
e578.TL = float(os.environ.get("E585_TL", "36000"))

if __name__ == "__main__":
    print(f"[E-585] large windowed-LNS FINE grid: walk n_steps={e578.WALK['n_steps']} "
          f"wait_dt={e578.WALK['wait_dt']} W=[{e578.WMIN},{e578.WMAX}] "
          f"seed={e578.SEED} vs bank {e578.CURRENT_BANK} -> {e578.OUT}", flush=True)
    e578.main()
