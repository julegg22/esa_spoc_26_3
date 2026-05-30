"""E-504 — Ch2 small wait_dt × n_steps × starting-node sweep.

Audit E-504: re-run greedy_findxfer + walk_perm_chrono across the
parameter grid (wait_dt, n_steps, start) — the hostile-default audit
flagged wait_dt=1.0 as the likely cause of 13.62 d idle in bank.

If any (start, wait_dt, n_steps) combination beats 142.92 d → immediate
bank improvement + confirms hostile-default class of bugs.

Grid (49 × 4 × 3 = 588 runs, each <30s; parallel):
  start ∈ {0..48}
  wait_dt ∈ {0.05, 0.1, 0.2, 1.0}  (1.0 = current default)
  n_steps ∈ {180, 360, 720}        (180 = current default)
"""
from __future__ import annotations
import sys, time, json
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_findtransfer_greedy import greedy_findxfer
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _task(args):
    start, wait_dt, n_steps, tof_window = args
    kt = _KT[0]
    # Greedy construction
    t0 = time.time()
    try:
        perm, times, tofs, dvs, ok = greedy_findxfer(
            kt, start=start, tof_window=tof_window, n_steps=n_steps,
            wait_steps=int(8 / max(wait_dt, 0.05)),  # cap ~8d total wait
            wait_dt=wait_dt, verbose=False)
    except Exception as e:
        return start, wait_dt, n_steps, None, None, str(e), time.time() - t0
    if not ok or len(perm) != kt.n:
        return start, wait_dt, n_steps, None, len(perm), "partial", time.time() - t0
    # Re-walk to recompute makespan with same params (consistent)
    times, tofs, dvs, ok, exc, k = walk_perm_chrono(
        kt, perm, tof_window=tof_window, n_steps=n_steps,
        wait_steps=int(8 / max(wait_dt, 0.05)), wait_dt=wait_dt)
    wall = time.time() - t0
    if not ok:
        return start, wait_dt, n_steps, None, k, "walk_infeasible", wall
    mk = times[-1] + tofs[-1]
    x = times + tofs + [float(p) for p in perm]
    fit = kt.fitness(x)
    if not kt.is_feasible(fit):
        return start, wait_dt, n_steps, None, k, f"UDP_infeasible:{list(fit)}", wall
    return start, wait_dt, n_steps, mk, exc, perm, wall


def main(workers=8):
    kt = KTTSP(INST)
    grid = []
    for start in range(kt.n):
        for wait_dt in (0.05, 0.1, 0.2, 1.0):
            for n_steps in (180, 360):  # drop 720 for compute
                grid.append((start, wait_dt, n_steps, 18.0))
    print(f"E-504: {len(grid)} runs (49 starts × 4 wait_dt × 2 n_steps), "
          f"parallel × {workers}", flush=True)

    t0 = time.time()
    results = []
    best = None
    with mp.Pool(workers, initializer=_init) as p:
        for i, r in enumerate(p.imap_unordered(_task, grid, chunksize=4)):
            results.append(r)
            start, wait_dt, n_steps, mk, exc, info, wall = r
            if mk is not None:
                if best is None or mk < best[0]:
                    best = (mk, start, wait_dt, n_steps, info, exc)
                    print(f"  [{i+1:3d}/{len(grid)}] start={start:2d} wait_dt={wait_dt:.2f} "
                          f"n_steps={n_steps:3d}: mk={mk:.4f}d exc={exc} "
                          f"({wall:.1f}s)  ★ NEW BEST", flush=True)
            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                pct = (i + 1) / len(grid) * 100
                print(f"  ({pct:.0f}% done, elapsed={elapsed:.0f}s, "
                      f"best={best[0]:.4f}d)", flush=True)
    wall = time.time() - t0

    print(f"\n=== E-504 complete in {wall:.0f}s ===", flush=True)
    print(f"bank=142.9183 d, R3=111.76 d, best in sweep="
          f"{best[0]:.4f} d", flush=True)
    if best[0] < 142.9183:
        print(f">>> IMPROVEMENT: {142.9183 - best[0]:.4f} d under bank", flush=True)
        print(f">>> Best config: start={best[1]} wait_dt={best[2]} n_steps={best[3]} exc={best[5]}",
               flush=True)
    else:
        print(f"  No improvement found in this grid; bank stays at 142.92 d",
              flush=True)

    # Also: cross-tab summary by (wait_dt, n_steps)
    print(f"\nCross-tab (best makespan per cell):", flush=True)
    print(f"{'wait_dt':>8s} | " + " ".join(f"{ns:>6d}" for ns in (180, 360)),
           flush=True)
    for wd in (0.05, 0.1, 0.2, 1.0):
        row = f"{wd:>8.2f} | "
        for ns in (180, 360):
            cell_results = [r[3] for r in results
                             if r[1] == wd and r[2] == ns and r[3] is not None]
            if cell_results:
                row += f"{min(cell_results):>6.2f}d "
            else:
                row += "  N/A  "
        print(row, flush=True)

    return {"best_mk_d": best[0] if best else None,
            "best_start": best[1] if best else None,
            "best_wait_dt": best[2] if best else None,
            "best_n_steps": best[3] if best else None,
            "best_perm": best[4] if best else None,
            "wall_s": wall, "n_runs": len(grid)}


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    res = main(workers=w)
    with open("/tmp/ch2_e504_results.json", 'w') as fh:
        json.dump(res, fh, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != 'best_perm'},
                     indent=2))
