"""E-741 — Ch2-LARGE: Warnsdorff-ordered backtracking DFS on the FAST faithful evaluator (E-739 batch_earliest).
The greedy beam walls at ~338/601 (structural bottleneck: it visits easy cities first and isolates the low-degree
E-729 cities). Fix = (a) MOST-CONSTRAINED-FIRST ordering (Warnsdorff: go to the neighbour with the fewest onward
unvisited options, so about-to-be-isolated cities get visited before they strand) + (b) BACKTRACKING on dead-ends.
Faithful arrivals via batch_earliest, cached by (last, epoch-bucket). Bounded by an expansion cap + branch cap.
Goal: a COMPLETE faithful 601-city comp0 path -> assemble + beat 932 (ideally 682).
Usage: CH2_MR=5 CH2_TOFHI=2.5 CH2_WAIT=2.5 CH2_BRANCH=6 CH2_MAXEXP=400000 python ch2_giant_backtrack.py"""
import os, sys, json, time
import numpy as np
sys.setrecursionlimit(5000)
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MINTOF = kt.min_tof; DAY = 86400.0
MR = int(os.environ.get("CH2_MR", "5")); TOFHI = float(os.environ.get("CH2_TOFHI", "2.5"))
WAIT = float(os.environ.get("CH2_WAIT", "2.5")); DSTEP = float(os.environ.get("CH2_DSTEP", "0.1"))
BRANCH = int(os.environ.get("CH2_BRANCH", "6")); MAXEXP = int(os.environ.get("CH2_MAXEXP", "400000"))

dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); _K = dz["keys"]; _V = dz["vals"]; _F = np.isfinite(_V)
NB = {}
for r, (i, j) in enumerate(_K):
    if _F[r].any():
        NB.setdefault(int(i), []).append((float(np.nanmin(_V[r])), int(j)))
for c in NB:
    NB[c].sort()
NBA = {c: np.array([j for _, j in v], dtype=np.int64) for c, v in NB.items()}
NBSET = {c: set(int(j) for _, j in v) for c, v in NB.items()}
CITIES = sorted(NB.keys()); NCITY = len(CITIES); IDX = {c: k for k, c in enumerate(CITIES)}
ft.batch_earliest(OPAR, CITIES[0], 100.0 * DAY, NBA[CITIES[0]][:3], 0.3 * DAY, DSTEP * DAY, MINTOF * DAY,
                  TOFHI * DAY, 0.02 * DAY, THR, MR)
_EC = {}                                                          # (last, t-bucket) -> (js[], arrs[]) feasible succ


def feas_succ(last, t_sec):
    key = (last, int(t_sec / DAY * 5))                           # 0.2d epoch bucket
    v = _EC.get(key)
    if v is not None:
        return v
    js = NBA.get(last)
    if js is None:
        _EC[key] = (np.empty(0, np.int64), np.empty(0)); return _EC[key]
    arrs, _ = ft.batch_earliest(OPAR, last, t_sec, js, WAIT * DAY, DSTEP * DAY, MINTOF * DAY,
                                TOFHI * DAY, 0.02 * DAY, THR, MR)
    ok = arrs > 0
    out = (js[ok], arrs[ok]); _EC[key] = out
    return out


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(CITIES); first = next(k for k, c in enumerate(order) if c in cset)
    start = order[first]; t0 = float(times[first]) * DAY
    print(f"[E-741] backtracking DFS: {NCITY} comp0, mr={MR} tofhi={TOFHI} wait={WAIT} branch={BRANCH} "
          f"maxexp={MAXEXP}; start {start} @ {t0/DAY:.1f}d (beam walled 338; r2=682 needs ~0.65 d/leg)", flush=True)
    visited = np.zeros(NCITY, dtype=bool); visited[IDX[start]] = True
    path = [start]; best = [1]; exp = [0]; t_start = time.time(); last_report = [0]

    def dfs(last, t_sec):
        if len(path) == NCITY:
            return True
        exp[0] += 1
        if exp[0] > MAXEXP:
            return False
        if len(path) > best[0]:
            best[0] = len(path)
            if best[0] % 25 == 0 or best[0] > 560 or time.time() - last_report[0] > 60:
                last_report[0] = time.time()
                print(f"[E-741] depth {best[0]}/{NCITY} ({(t_sec/DAY-t0/DAY)/max(best[0]-1,1):.3f} d/leg) "
                      f"exp={exp[0]} cache={len(_EC)} [{time.time()-t_start:.0f}s]", flush=True)
        js, arrs = feas_succ(last, t_sec)
        # candidate = unvisited feasible successors; order MOST-CONSTRAINED-FIRST (Warnsdorff), tie earliest arrival
        cand = []
        for q in range(len(js)):
            j = int(js[q])
            if visited[IDX[j]]:
                continue
            deg = 0                                              # onward unvisited cheap options of j
            for jj in NBSET.get(j, ()):
                if not visited[IDX[jj]]:
                    deg += 1
            cand.append((deg, float(arrs[q]), j))
        if not cand:
            return False
        cand.sort()                                              # fewest onward options first, then earliest arrival
        for _, arr, j in cand[:BRANCH]:
            visited[IDX[j]] = True; path.append(j)
            if dfs(j, arr):
                return True
            path.pop(); visited[IDX[j]] = False
            if exp[0] > MAXEXP:
                return False
        return False

    done = dfs(start, t0)
    if done:
        fin = None
        # recompute finish by walking the path faithfully (greedy earliest)
        t = t0
        for k in range(len(path) - 1):
            js, arrs = feas_succ(path[k], t)
            idx = list(js).index(path[k + 1]) if path[k + 1] in list(js) else -1
            t = float(arrs[idx]) if idx >= 0 else t
        json.dump({"path": path, "finish_d": t / DAY, "d_leg": (t / DAY - t0 / DAY) / (NCITY - 1)},
                  open(f"{ROOT}/cache/ch2_giant_backtrack_complete.json", "w"))
        print(f"[E-741] *** COMPLETE {NCITY}! finish {t/DAY:.1f}d ({(t/DAY-t0/DAY)/(NCITY-1):.3f} d/leg) "
              f"[{time.time()-t_start:.0f}s]", flush=True)
    else:
        print(f"[E-741] DONE no complete tour; best depth {best[0]}/{NCITY} exp={exp[0]} "
              f"(greedy beam walled 338) [{time.time()-t_start:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
