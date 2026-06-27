"""E-732 — Ch2-large rank-1: anytime A* / bounded best-first search over the TD-TSPTW (user-requested).

The metaheuristics walled at rank-2 (basin-unreachability). This tries the one principled lever that fits the
time budget: an ANYTIME best-first search with an admissible lower bound, f = g + h, where
  g = current arrival time (includes waiting so far),
  h = sum over UNVISITED cities of their minimum cheap incoming tof  (admissible LB on remaining flight time;
      true remaining = flight + waits >= flight >= h).
So f is an admissible lower bound on the final makespan -> best-first by f explores the tightest-phased
(low-wait) partial tours first, which is exactly the rank-1 regime the depth-greedy beam under-explored.
Memory-bounded (cap the open list) -> anytime, not exact. Cheap (short-tof) successors only for the giant
(strongly connected on short-tof per E-726); exceptions left out of the prototype.
Usage: python ch2_giant_anytime_astar.py [MAXOPEN=200000] [Kbranch=12] [maxwait=12] [hbias=1.0]"""
import sys, os, json, time, heapq
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
WIN = np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item()
cities = sorted(set(int(i) for ij in WIN for i in ij))
NG = len(cities)
cidx = {c: k for k, c in enumerate(cities)}                    # bit index per city
OUT = {c: [] for c in cities}                                  # out-neighbours (short-tof), sorted by min-tof
MIN_IN = {c: 9.9 for c in cities}                              # min cheap incoming tof (for the LB)
for (i, j), (deps, tofs) in WIN.items():
    if i in cidx and j in cidx and len(tofs) > 0:
        mt = float(np.min(tofs))
        OUT[i].append((j, mt))
        MIN_IN[j] = min(MIN_IN[j], mt)
for c in OUT:
    OUT[c].sort(key=lambda x: x[1])
MININ = np.array([MIN_IN[c] for c in cities])
H_ALL = float(MININ.sum())
print(f"[E-732] giant n={NG}; H_all(sum min-in tof)={H_ALL:.1f}d; "
      f"sum over 601 legs at min-tof = a hard LB on any complete tour's flight time", flush=True)


def earliest(i, j, t, maxwait):
    w = WIN.get((i, j))
    if w is None:
        return None
    deps, tofs = w
    q = np.searchsorted(deps, t)
    if q < len(deps) and deps[q] <= t + maxwait:
        return float(deps[q] + tofs[q])
    return None


def main(MAXOPEN=200000, Kbranch=12, maxwait=12.0, hbias=1.0):
    start = cities[0]
    # node store (parent pointers) -> memory-light
    P_par = [-1]; P_city = [start]; P_h = [H_ALL - MIN_IN[start]]
    # open heap entries: (f, g, exc, depth, mask, node_idx)
    mask0 = 1 << cidx[start]
    openh = [(hbias * P_h[0], 0.0, 0, 1, mask0, 0)]
    best_depth = 1; best_mk = float("inf"); best_node = 0
    bestseen = {}                                              # (last, depth) -> min g  (dominance prune)
    t0 = time.time(); popped = 0; ckpt = f"{ROOT}/cache/ch2_giant_astar_best.json"
    while openh and popped < 60_000_000:
        f, g, exc, depth, mask, ni = heapq.heappop(openh)
        popped += 1
        last = P_city[ni]
        if depth == NG:                                       # complete tour (anytime)
            if g < best_mk:
                best_mk = g
                path = []; k = ni
                while k != -1:
                    path.append(P_city[k]); k = P_par[k]
                path.reverse()
                json.dump({"path": path, "makespan": g}, open(ckpt, "w"))
                print(f"[E-732] *** COMPLETE 601 makespan {g:.1f}d (d/leg {g/600:.3f}) "
                      f"{'RANK-1!' if g < 425 else ''} [{time.time()-t0:.0f}s pop {popped}]", flush=True)
            continue
        if depth > best_depth:
            best_depth = depth; best_node = ni
            if depth % 10 == 0 or depth > 560:
                print(f"[E-732] depth {depth}/{NG} g={g:.1f}d f={f:.1f} d/leg {g/max(depth-1,1):.3f} "
                      f"|open|={len(openh)} [{time.time()-t0:.0f}s pop {popped}]", flush=True)
        # expand: cheap successors not visited, earliest arrival; child h = parent h - min-in(child)
        hp = P_h[ni]; cnt = 0
        for (j, _mt) in OUT[last]:
            if mask >> cidx[j] & 1:
                continue
            a = earliest(last, j, g, maxwait)
            if a is None:
                continue
            key = (j, depth + 1)
            if key in bestseen and bestseen[key] <= a + 1e-9:
                continue                                      # dominated: later/equal arrival at same (city,depth)
            bestseen[key] = a
            h_child = hp - MIN_IN[j]
            P_par.append(ni); P_city.append(j); P_h.append(h_child); nj = len(P_par) - 1
            heapq.heappush(openh, (a + hbias * h_child, a, exc, depth + 1, mask | (1 << cidx[j]), nj))
            cnt += 1
            if cnt >= Kbranch:
                break
        if len(openh) > MAXOPEN:                              # prune worst-f to bound memory (anytime, not exact)
            openh = heapq.nsmallest(MAXOPEN * 3 // 4, openh)
            heapq.heapify(openh)
    print(f"[E-732] DONE best_depth {best_depth}/{NG} best_mk {best_mk if best_mk<9e9 else 'none'} "
          f"[{time.time()-t0:.0f}s pop {popped}]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 200000, int(a[2]) if len(a) > 2 else 12,
         float(a[3]) if len(a) > 3 else 12.0, float(a[4]) if len(a) > 4 else 1.0)
