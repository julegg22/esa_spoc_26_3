"""E-739 — Ch2-LARGE: faithful GLOBAL beam on the FAST BATCHED evaluator (ch2_fast_transfer.batch_earliest).
The genuine lever from E-735: prior beams were too slow (faithful eval ~250ms/edge) OR ran on an optimistic table.
batch_earliest evaluates earliest cheap arrival to ALL of a city's neighbours in one numba-parallel call
(~5ms/nbr at max_revs=3, validated to 1e-11 vs official). This makes a faithful 601-city beam tractable (~2-3hr).

Beam: states at uniform depth, dominance by last-city (min arrival), width BW. Expansion = batch_earliest over
unvisited cheap neighbours, keep K cheapest-arrival. Complete 601-tour finish < bank comp0 (~876d) at <0.65 d/leg
=> rank-2 (beat r2=682). Restricting to short-tof (tof_hi~2, low rev) forces the short-hop rank-1 regime.
Usage: CH2_BW=30 CH2_K=10 CH2_MR=3 CH2_TOFHI=2.0 CH2_WAIT=2.0 python ch2_giant_fasteval_beam.py"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MINTOF = kt.min_tof; DAY = 86400.0
BW = int(os.environ.get("CH2_BW", "30")); KEXP = int(os.environ.get("CH2_K", "10"))
MR = int(os.environ.get("CH2_MR", "3")); TOFHI = float(os.environ.get("CH2_TOFHI", "2.0"))
WAIT = float(os.environ.get("CH2_WAIT", "2.0")); DSTEP = float(os.environ.get("CH2_DSTEP", "0.1"))

dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); _K = dz["keys"]; _V = dz["vals"]; _F = np.isfinite(_V)
NB = {}
for r, (i, j) in enumerate(_K):
    if _F[r].any():
        NB.setdefault(int(i), []).append((float(np.nanmin(_V[r])), int(j)))
for c in NB:
    NB[c].sort()
NBA = {c: np.array([j for _, j in v], dtype=np.int64) for c, v in NB.items()}   # cheap out-neighbours per city
CITIES = sorted(NB.keys()); NCITY = len(CITIES); IDX = {c: k for k, c in enumerate(CITIES)}
# warm jit
ft.batch_earliest(OPAR, CITIES[0], 100.0 * DAY, NBA[CITIES[0]][:3], 0.3 * DAY, DSTEP * DAY, MINTOF * DAY,
                  TOFHI * DAY, 0.02 * DAY, THR, MR)


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(CITIES)
    first = next(k for k, c in enumerate(order) if c in cset)
    start = order[first]; t0 = float(times[first]) * DAY
    print(f"[E-739] fast-eval beam: {NCITY} comp0, BW={BW} K={KEXP} mr={MR} tofhi={TOFHI} wait={WAIT} dstep={DSTEP}; "
          f"start {start} @ {t0/DAY:.1f}d (bank comp0 ~1.46 d/leg; r2=682 needs ~0.65)", flush=True)
    P_par = [-1]; P_city = [start]
    beam = [(t0, start, 1 << IDX[start], 0)]
    best_depth = 1; tstart = time.time(); bestnode = 0
    for depth in range(1, NCITY):
        cand = {}                                                # last_city -> (arr, mask, node_idx)
        for (arr, last, mask, ni) in beam:
            js = NBA.get(last)
            if js is None:
                continue
            unv = js[[(mask >> IDX[j] & 1) == 0 for j in js]]     # unvisited cheap neighbours
            if len(unv) == 0:
                continue
            arrs, tofs = ft.batch_earliest(OPAR, last, arr, unv, WAIT * DAY, DSTEP * DAY, MINTOF * DAY,
                                           TOFHI * DAY, 0.02 * DAY, THR, MR)
            ok = np.where(arrs > 0)[0]
            if len(ok) == 0:
                continue
            o = ok[np.argsort(arrs[ok])[:KEXP]]                  # K earliest arrivals
            for idx in o:
                j = int(unv[idx]); na = float(arrs[idx])
                prev = cand.get(j)
                if prev is None or na < prev[0]:
                    cand[j] = (na, mask | (1 << IDX[j]), ni)
        if not cand:
            print(f"[E-739] STRANDED depth {depth}/{NCITY} [{time.time()-tstart:.0f}s]", flush=True); break
        items = sorted(cand.items(), key=lambda kv: kv[1][0])[:BW]
        beam = []
        for j, (na, mask, par) in items:
            P_par.append(par); P_city.append(j); beam.append((na, j, mask, len(P_par) - 1))
        d = depth + 1; bestnode = beam[0][3]
        if d > best_depth:
            best_depth = d
        if d == NCITY:
            na = beam[0][0]
            path = []; k = beam[0][3]
            while k != -1:
                path.append(P_city[k]); k = P_par[k]
            path.reverse()
            dleg = (na / DAY - t0 / DAY) / (NCITY - 1)
            json.dump({"path": path, "finish_d": na / DAY, "d_leg": dleg}, open(f"{ROOT}/cache/ch2_giant_fasteval_complete.json", "w"))
            print(f"[E-739] *** COMPLETE {NCITY}! finish {na/DAY:.1f}d ({dleg:.3f} d/leg) "
                  f"{'BEATS r2=682!' if na/DAY*NCITY/600 < 682 else ''} [{time.time()-tstart:.0f}s]", flush=True)
            break
        if d % 25 == 0 or d > 560:
            ba = beam[0][0] / DAY
            print(f"[E-739] depth {d}/{NCITY}: arr {ba:.1f}d ({(ba-t0/DAY)/max(d-1,1):.3f} d/leg) |beam|={len(beam)} "
                  f"[{time.time()-tstart:.0f}s]", flush=True)
    if best_depth < NCITY:
        print(f"[E-739] DONE best_depth {best_depth}/{NCITY} (prior optimistic-table beams 558-575; faithful 191) "
              f"[{time.time()-tstart:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
