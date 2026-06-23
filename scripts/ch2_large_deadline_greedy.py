"""E-709c — Ch2-large experiment #1: WINDOW-DEADLINE greedy on the giant (the untried urgency metric).
Prior constructions ordered by node DEGREE (E-666, failed at 350/601). But the giant is a narrow-window
(~32d, 1.1% horizon) time-dependent TSP, so the right urgency is WINDOW-CLOSING-TIME, not degree. Uses
the cached 1d table (vals[pair,epoch]=min cheap tof or inf) for window timing; construction is pure
array lookups (fast). Tests several selection metrics; reports how far each threads vs the 350 wall.
Usage: python ch2_large_deadline_greedy.py"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]            # (950,), (74208,2), (74208,950)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
# adjacency: out_neighbors[i] = list of (j, row_index)
from collections import defaultdict
out = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    out[int(i)].append((int(j), r))
# precompute per row: earliest epoch finite, latest epoch finite (the window span)
fin = np.isfinite(VALS)
first_e = np.where(fin.any(1), EPOCHS[fin.argmax(1)], np.inf)
last_idx = (VALS.shape[1] - 1) - fin[:, ::-1].argmax(1)
last_e = np.where(fin.any(1), EPOCHS[last_idx], -np.inf)


def run(metric, start, exc_budget=5):
    visited = {start}; order = [start]; t = 0.0; strands = 0; exc = 0
    while len(visited) < NG:
        cur = order[-1]; cands = []
        for (j, r) in out[cur]:
            if j in visited:
                continue
            v = VALS[r]; mask = (EPOCHS >= t) & np.isfinite(v)
            if not mask.any():
                continue
            es = EPOCHS[mask]; tofs = v[mask]; arr = es + tofs
            bi = int(np.argmin(arr))
            cands.append((j, float(arr[bi]), float(es[mask.sum() - 1] if False else es[-1]), float(last_e[r])))
        if not cands:
            strands += 1
            break
        if metric == "min_arrival":
            j, arr, _, _ = min(cands, key=lambda c: c[1])
        elif metric == "edf":                                # earliest window-close deadline
            j, arr, _, _ = min(cands, key=lambda c: c[3])
        elif metric == "edf_reachable":                      # among soon-reachable, earliest deadline
            soon = [c for c in cands if c[1] <= t + 30]
            pool = soon if soon else cands
            j, arr, _, _ = min(pool, key=lambda c: c[3])
        order.append(j); visited.add(j); t = arr
    return len(visited), strands, t, order


def main():
    print(f"[E-709c] giant n={NG}; testing window-deadline metrics (baseline degree-greedy stranded ~350/601)", flush=True)
    start = cities[0]
    for metric in ["min_arrival", "edf", "edf_reachable"]:
        best = (0, None)
        t0 = time.time()
        for s in cities[:30]:                                # try 30 starts
            nv, strands, mk, order = run(metric, s)
            if nv > best[0]:
                best = (nv, (s, strands, mk, order))
        nv, (s, strands, mk, order) = best
        flag = "  ** THREADS PAST 350! **" if nv > 360 else ""
        print(f"  metric={metric:14s}: best threads {nv}/{NG} (start {s}, strands={strands}, mk~{mk:.0f}d) [{time.time()-t0:.0f}s]{flag}", flush=True)
        if nv > 360:
            json.dump({"metric": metric, "visited": nv, "order": order}, open(f"/tmp/ch2_deadline_{metric}.json", "w"))
    print("[E-709c] VERDICT: if any metric threads >>350 -> window-deadline ordering breaks the wall (degree was the wrong proxy). "
          "If all ~350 -> the wall is global, needs full TD-TSP (VRPTW/time-expanded).", flush=True)


if __name__ == "__main__":
    main()
