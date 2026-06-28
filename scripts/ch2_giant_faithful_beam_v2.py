"""E-735 probe #1c — Ch2-LARGE: FAITHFUL global beam constructor for comp0 (601 cities), built on the FINE LOCAL
ORACLE (cheap_first_tof over [t,t+W] at 0.02d) that reproduces the bank exactly. Prior beams (E-710) reached
558-575/601 but on the OPTIMISTIC sparse table; this is the first beam on a FAITHFUL evaluator.

Beam: states at uniform depth, dominance by last-city (keep min-arrival), width BW. Each state expands to up to K
cheapest-min-tof unvisited neighbours, earliest faithful arrival via the oracle. Tracks deepest path + min arrival;
a COMPLETE 601 path's finish < bank comp0 portion (~876d) at <0.65 d/leg => rank-2 lever.
Usage: CH2_BW=40 CH2_K=10 CH2_WAIT=6 python ch2_giant_faithful_beam_v2.py"""
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
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = kt.min_tof; DAY = 86400.0
BW = int(os.environ.get("CH2_BW", "40")); K = int(os.environ.get("CH2_K", "10"))
WAIT = float(os.environ.get("CH2_WAIT", "6.0")); DSTEP = float(os.environ.get("CH2_DSTEP", "0.02"))
START = os.environ.get("CH2_START", "bank")                      # 'bank' or a city id
TOFHI = float(os.environ.get("CH2_TOFHI", "8.5"))

# cheap adjacency + per-city neighbours sorted by min-tof (static order to try)
dz = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); _K = dz["keys"]; _V = dz["vals"]; _F = np.isfinite(_V)
NB = {}
for r, (i, j) in enumerate(_K):
    if _F[r].any():
        NB.setdefault(int(i), []).append((float(np.nanmin(_V[r])), int(j)))
for c in NB:
    NB[c].sort()
CITIES = sorted(NB.keys()); NCITY = len(CITIES); IDX = {c: k for k, c in enumerate(CITIES)}
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, TOFHI * DAY, DSTEP * DAY, THR, MAXREV)
_EC = {}


def earliest(i, j, t):
    key = (i, j, int(t * 5))
    v = _EC.get(key, 0)
    if v != 0:
        return v
    deps = np.arange(t, t + WAIT, DSTEP)
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, TOFHI * DAY, DSTEP * DAY, THR, MAXREV)
    m = tof > 0
    if not m.any():
        _EC[key] = None; return None
    arr = deps[m] + tof[m] / DAY; k = int(np.argmin(arr))
    out = float(arr[k]); _EC[key] = out
    return out


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(CITIES)
    first = next(k for k, c in enumerate(order) if c in cset)
    start_city = order[first] if START == "bank" else int(START)
    t0_epoch = float(times[first])
    print(f"[E-735c] faithful beam: {NCITY} comp0 cities, BW={BW} K={K} WAIT={WAIT} dstep={DSTEP}; "
          f"start city {start_city} @ t={t0_epoch:.1f} (bank comp0 portion ~876d / 601 = 1.46 d/leg; "
          f"r2=682 needs comp0 d/leg ~0.65)", flush=True)
    # node store: parent index + city; beam holds node indices
    P_par = [-1]; P_city = [start_city]
    beam = [(t0_epoch, start_city, 1 << IDX[start_city], 0)]     # (arr, last, mask, node_idx)
    best_depth = 1; best_complete = None; t_start = time.time()
    for depth in range(1, NCITY):
        cand = {}                                                # last_city -> (arr, mask, node_idx)
        for (arr, last, mask, ni) in beam:
            cnt = 0
            for (mt, nxt) in NB[last]:
                if mask >> IDX[nxt] & 1:
                    continue
                na = earliest(last, nxt, arr)
                if na is None:
                    continue
                prev = cand.get(nxt)
                if prev is None or na < prev[0]:
                    cand[nxt] = (na, mask | (1 << IDX[nxt]), ni)
                cnt += 1
                if cnt >= K:
                    break
        if not cand:
            print(f"[E-735c] STRANDED at depth {depth}/{NCITY} (no successors) [{time.time()-t_start:.0f}s]", flush=True)
            break
        # build new beam: top-BW by arrival, create nodes
        items = sorted(cand.items(), key=lambda kv: kv[1][0])[:BW]
        newbeam = []
        for nxt, (na, mask, par_ni) in items:
            P_par.append(par_ni); P_city.append(nxt); nj = len(P_par) - 1
            newbeam.append((na, nxt, mask, nj))
        beam = newbeam
        d = depth + 1
        if d > best_depth:
            best_depth = d
        if d == NCITY:                                           # complete tour(s) in beam
            na, last, mask, ni = beam[0]
            best_complete = (na, ni)
            print(f"[E-735c] *** COMPLETE {NCITY} cities! finish {na:.2f}d (dur {na-t0_epoch:.1f}d, "
                  f"{(na-t0_epoch)/(NCITY-1):.3f} d/leg) [{time.time()-t_start:.0f}s]", flush=True)
            break
        if d % 25 == 0 or d > 550:
            ba = beam[0][0]
            print(f"[E-735c] depth {d}/{NCITY}: best_arr {ba:.1f}d ({(ba-t0_epoch)/max(d-1,1):.3f} d/leg) "
                  f"|beam|={len(beam)} cache={len(_EC)} [{time.time()-t_start:.0f}s]", flush=True)
    # report
    if best_complete:
        na, ni = best_complete
        path = []; k = ni
        while k != -1:
            path.append(P_city[k]); k = P_par[k]
        path.reverse()
        json.dump({"path": path, "finish": na, "t0": t0_epoch, "d_leg": (na - t0_epoch) / (NCITY - 1)},
                  open(f"{ROOT}/cache/ch2_giant_faithful_beam_complete.json", "w"))
        print(f"[E-735c] DONE complete comp0: {na:.2f}d, {(na-t0_epoch)/(NCITY-1):.3f} d/leg "
              f"(vs bank comp0 ~1.46; {'BEATS' if na-t0_epoch < 876 else 'above'} bank comp0 dur ~876d)", flush=True)
    else:
        print(f"[E-735c] DONE no complete tour; best depth {best_depth}/{NCITY} "
              f"(prior optimistic-table beams: 558-575) [{time.time()-t_start:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
