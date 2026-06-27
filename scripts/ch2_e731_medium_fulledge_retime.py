"""E-040 (script e568): Ch2 medium — ULTRAFINE re-time of the banked perm.

The medium bank (195.7748d, E-563) was final-timed on a 160-point tof
grid (0.075d spacing) with a 0.1d t-quantum. Live board 2026-06-12:
r1 = 195.6816 — only 0.093d above the bank, i.e. ~one grid step. This
script re-times the UNCHANGED bank perm on a 2x denser grid (320 tofs,
0.05d t-quantum) with an exact forward DP. Small's E-529 showed
fine->ultrafine re-timing alone recovers real days; here we need 0.094.

Writes candidate to /tmp ONLY (guard-banking is a separate step).
"""

import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from numba import njit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP  # noqa: E402

PROB = os.environ.get("E568_PROB", "medium")  # medium | small | large
_KFILE = {"medium": "medium", "small": "easy", "large": "hard"}[PROB]
_BFILE = {"medium": "medium", "small": "small", "large": "large"}[PROB]
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        f"Salesperson Problem/problems/{_KFILE}.kttsp")
BANK = f"{ROOT}/solutions/upload/{_BFILE}.json"
OUT = f"/tmp/ch2_{PROB}_ultrafine_candidate.json"

TQ = float(os.environ.get("E568_TQ", "0.05"))
N_TOF = int(os.environ.get("E568_NTOF", "320"))
WORKERS = int(os.environ.get("E568_WORKERS", "2"))

TOFS = np.linspace(0.01, 12.0, N_TOF)
TSTARTS = np.arange(0.0, 500.0, TQ)
INF_INT = 10 ** 9

_KT = [None]


def _init(inst):
    _KT[0] = KTTSP(inst)


def _scan(args):
    k, i, j = args
    kt = _KT[0]
    nt = len(TSTARTS)
    cheap = np.full(nt, np.inf, dtype=np.float32)
    exc = np.full(nt, np.inf, dtype=np.float32)
    for ki, ts in enumerate(TSTARTS):
        if ts + TOFS[-1] > kt.max_time:
            break
        for tof in TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= 100.0:
                cheap[ki] = tof
                exc[ki] = tof
                break
            elif dv <= 600.0 and tof < exc[ki]:
                exc[ki] = tof
    return k, cheap, exc


@njit(cache=True)
def _forward_dp_fast(c_arr, e_arr, T, n_legs, nexc):
    reach = np.zeros((n_legs + 1, T, nexc + 1), dtype=np.bool_)
    pred_dep = np.full((n_legs + 1, T, nexc + 1), -1, dtype=np.int32)
    pred_e = np.full((n_legs + 1, T, nexc + 1), -1, dtype=np.int8)
    pred_ix = np.full((n_legs + 1, T, nexc + 1), -1, dtype=np.int8)
    reach[0, 0, 0] = True
    for k in range(n_legs):
        for e in range(nexc + 1):
            tmin = -1
            for t in range(T):
                if reach[k, t, e]:
                    tmin = t
                    break
            if tmin < 0:
                continue
            # any departure tp >= tmin is reachable from SOME reached state
            for tp in range(tmin, T):
                arr = c_arr[k, tp]
                if arr < INF_INT and arr < T and not reach[k + 1, arr, e]:
                    reach[k + 1, arr, e] = True
                    pred_dep[k + 1, arr, e] = tp
                    pred_e[k + 1, arr, e] = e
                    pred_ix[k + 1, arr, e] = 0
                if e < nexc:
                    arr2 = e_arr[k, tp]
                    if (arr2 < INF_INT and arr2 < T
                            and not reach[k + 1, arr2, e + 1]):
                        reach[k + 1, arr2, e + 1] = True
                        pred_dep[k + 1, arr2, e + 1] = tp
                        pred_e[k + 1, arr2, e + 1] = e
                        pred_ix[k + 1, arr2, e + 1] = 1
    return reach, pred_dep, pred_e, pred_ix


def main():
    kt = KTTSP(INST)
    n = kt.n
    nexc = kt.n_exc
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm = [int(v) for v in bank[2 * (n - 1):]]
    bank_mk = float(kt.fitness(bank)[0])
    print(f"[BASE] bank mk={bank_mk:.4f} | grid TQ={TQ} N_TOF={N_TOF} "
          f"T={len(TSTARTS)} workers={WORKERS}", flush=True)

    n_legs = n - 1
    nt = len(TSTARTS)
    legs = [(k, perm[k], perm[k + 1]) for k in range(n_legs)]
    cheap = np.full((n_legs, nt), np.inf, dtype=np.float32)
    exc = np.full((n_legs, nt), np.inf, dtype=np.float32)
    t0 = time.time()
    with mp.Pool(WORKERS, initializer=_init, initargs=(INST,)) as p:
        done = 0
        for k, c, e in p.imap_unordered(_scan, legs, chunksize=1):
            cheap[k] = c
            exc[k] = e
            done += 1
            if done % 20 == 0:
                print(f"  [SCAN] {done}/{n_legs} legs "
                      f"({time.time()-t0:.0f}s)", flush=True)
    print(f"[SCAN] done in {time.time()-t0:.0f}s", flush=True)

    c_arr = np.full((n_legs, nt), INF_INT, dtype=np.int32)
    c_tof = np.full((n_legs, nt), np.nan, dtype=np.float32)
    e_arr = np.full((n_legs, nt), INF_INT, dtype=np.int32)
    e_tof = np.full((n_legs, nt), np.nan, dtype=np.float32)
    for k in range(n_legs):
        for tp in range(nt):
            cv = cheap[k, tp]
            if np.isfinite(cv):
                c_tof[k, tp] = cv
                a = tp + int(np.ceil(float(cv) / TQ))
                if a < nt:
                    c_arr[k, tp] = a
            ev = exc[k, tp]
            if np.isfinite(ev):
                e_tof[k, tp] = ev
                a = tp + int(np.ceil(float(ev) / TQ))
                if a < nt:
                    e_arr[k, tp] = a

    print("[DP] forward DP...", flush=True)
    t0 = time.time()
    reach, pd, pe, pix = _forward_dp_fast(c_arr, e_arr, nt, n_legs, nexc)
    sink = reach[n_legs]
    rows = np.where(sink.any(axis=1))[0]
    if len(rows) == 0:
        print("[DP] no feasible sink — NOTHING.", flush=True)
        return
    min_t = int(rows.min())
    e_used = int(np.where(sink[min_t])[0].min())
    print(f"[DP] sink bucket={min_t} ({min_t*TQ:.2f}d) exc={e_used} "
          f"({time.time()-t0:.0f}s)", flush=True)

    # decode: walk back, predecessor arrival = earliest reached bucket
    times = [0.0] * n_legs
    tofs = [0.0] * n_legs
    k, t, e = n_legs, min_t, e_used
    while k > 0:
        dep = int(pd[k, t, e])
        isx = int(pix[k, t, e])
        e_prev = int(pe[k, t, e])
        times[k - 1] = dep * TQ
        tofs[k - 1] = float(e_tof[k - 1, dep] if isx else c_tof[k - 1, dep])
        k -= 1
        e = e_prev
        if k > 0:
            cand = np.where(reach[k, :dep + 1, e])[0]
            assert len(cand) > 0, "broken backtrack"
            t = int(cand.min())

    x = list(times) + list(tofs) + [float(p) for p in perm]
    fit = kt.fitness(x)
    feas = bool(kt.is_feasible(fit))
    mk = float(fit[0])
    print(f"[VERDICT] ultrafine mk={mk:.4f} feas={feas} "
          f"viols={list(fit[1:])} | bank={bank_mk:.4f} "
          f"delta={mk-bank_mk:+.4f}", flush=True)

    json.dump([{"decisionVector": x,
                "problem": PROB,
                "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
              open(OUT, "w"))
    print(f"[OUT] candidate written to {OUT} "
          f"({'BEATS BANK' if feas and mk < bank_mk - 1e-9 else 'no gain'})",
          flush=True)


if __name__ == "__main__":
    main()
