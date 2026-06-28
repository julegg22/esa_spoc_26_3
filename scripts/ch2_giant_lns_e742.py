"""E-742 — Ch2-LARGE global LNS on the COMPLETE bank tour (user: secure rank-3 with more headroom).
A faithful full-1051-tour re-timer (greedy earliest-arrival; cheap dv<=100 except the 5 exc bridges dv<=600,
via the numba cheap_first_tof evaluator) is BOTH (a) the assembler that realizes the E-735 finesearch comp0-segment
improvements into the bank, and (b) the evaluator for a destroy-repair LNS that pushes the makespan lower.
Stage 1 (this run): assemble finesearch segments + guard-bank if <932 + feasible. Stage 2: LNS.
Usage: python ch2_giant_lns_e742.py"""
import os, sys, json, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64); THR = kt.dv_thr; EXC = kt.dv_exc; MINTOF = kt.min_tof; DAY = 86400.0
MR = int(os.environ.get("CH2_MR", "8")); WAIT = float(os.environ.get("CH2_WAIT", "4.0"))
DSTEP = float(os.environ.get("CH2_DSTEP", "0.02")); TOFHI = float(os.environ.get("CH2_TOFHI", "8.0"))
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, TOFHI * DAY, DSTEP * DAY, THR, MR)
_EC = {}


def earliest(i, j, t_d, thr):
    key = (i, j, int(t_d * 50), int(thr))
    v = _EC.get(key)
    if v is not None:
        return v
    deps = np.arange(t_d, t_d + WAIT, DSTEP)
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, TOFHI * DAY, DSTEP * DAY, thr, MR)
    m = tof > 0
    if not m.any():
        _EC[key] = None; return None
    arr = deps[m] + tof[m] / DAY; k = int(np.argmin(arr))
    out = (float(deps[m][k]), float(tof[m][k] / DAY), float(arr[k])); _EC[key] = out
    return out


def retime_full(order, bridge_pos, t0=0.0):
    nl = len(order) - 1; times = np.empty(nl); tofs = np.empty(nl); t = t0
    for k in range(nl):
        thr = EXC if k in bridge_pos else THR
        r = earliest(order[k], order[k + 1], t, thr)
        if r is None:
            return None, k
        times[k] = r[0]; tofs[k] = r[1]; t = r[2]
    return (times, tofs), nl


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; b_order = [int(c) for c in bank[2 * (N - 1):]]
    f0 = kt.fitness(bank); print(f"[E-742] bank kt.fitness {float(f0[0]):.2f}d", flush=True)
    bt = np.array(bank[:N - 1]); bf = np.array(bank[N - 1:2 * (N - 1)])
    bridge_pos = set(k for k in range(N - 1)
                     if kt.compute_transfer(b_order[k], b_order[k + 1], float(bt[k]), float(bf[k])) > THR + 1e-6)
    print(f"[E-742] {len(bridge_pos)} exc bridge legs at {sorted(bridge_pos)}", flush=True)
    t0 = time.time()
    res = retime_full(b_order, bridge_pos)
    if res[0] is None:
        print(f"[E-742] POS-CONTROL bank order STRANDS at leg {res[1]} [{time.time()-t0:.0f}s]", flush=True); return
    ti, tf = res[0]; fit = kt.fitness(list(ti) + list(tf) + [float(c) for c in b_order])
    print(f"[E-742] POS-CONTROL retimed bank {float(fit[0]):.2f}d feas={max(float(x) for x in fit[1:])<=1e-6} "
          f"(vs 932.53) [{time.time()-t0:.0f}s]", flush=True)
    cset = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)
    segs = []; k = 0
    while k < N:
        if b_order[k] in cset:
            s = k
            while k < N and b_order[k] in cset:
                k += 1
            segs.append((s, k))
        else:
            k += 1
    new_order = list(b_order); applied = 0
    for si, (s, e) in enumerate(segs):
        f = f"{ROOT}/cache/ch2_giant_comp0_fine_f{si}_seg{si}.json"
        if not os.path.exists(f):
            continue
        fc = [int(c) for c in json.load(open(f))["cities"]]
        if set(fc) == set(b_order[s:e]) and len(fc) == e - s:
            new_order[s:e] = fc; applied += 1
    print(f"[E-742] assembled finesearch into {applied}/{len(segs)} comp0 segments", flush=True)
    res2 = retime_full(new_order, bridge_pos)
    if res2[0] is None:
        print(f"[E-742] assembled order strands at leg {res2[1]} [{time.time()-t0:.0f}s]", flush=True); return
    ti2, tf2 = res2[0]; dv2 = list(ti2) + list(tf2) + [float(c) for c in new_order]
    fit2 = kt.fitness(dv2); mk2 = float(fit2[0]); feas2 = max(float(x) for x in fit2[1:]) <= 1e-6
    print(f"[E-742] ASSEMBLED makespan {mk2:.2f}d feas={feas2} (gain {932.53-mk2:+.2f}d) [{time.time()-t0:.0f}s]", flush=True)
    if feas2 and mk2 < 932.53 - 0.5:
        shutil.copy(f"{ROOT}/solutions/upload/large.json", f"{ROOT}/solutions/upload/large.json.bak_lns1")
        json.dump([{"decisionVector": [float(x) for x in dv2], "problem": "hard",
                    "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                  open(f"{ROOT}/solutions/upload/large.json", "w"))
        rt = kt.fitness(json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"])
        print(f"[E-742] GUARD-BANKED large -> {float(rt[0]):.2f}d; rank-3 headroom vs next 1028.59 = "
              f"{1028.59-float(rt[0]):.0f}d. NOT submitted.", flush=True)
    else:
        print(f"[E-742] no bankable gain ({mk2:.2f})", flush=True)


if __name__ == "__main__":
    main()
