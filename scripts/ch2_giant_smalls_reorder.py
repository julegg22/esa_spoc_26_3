"""E-743 — Ch2-LARGE: reorder the 3 SMALL clusters (the untapped headroom). The bank's smalls run at ~0.44 d/leg
(66-80d each) but are TD-greedy-solvable at ~0.08 d/leg (probe: largest small 66.1d->12.0d). All prior reorder
work was on comp0; the smalls were never touched. Endpoint-constrained (keep each small's first+last city = the
bridge gateways) greedy-NN + or-opt with the fast faithful oracle, from each small's bank entry epoch; splice into
the tour; faithful full-tour re-time (mr=20) + guard-bank.
Usage: python ch2_giant_smalls_reorder.py"""
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
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), MINTOF * DAY, 8 * DAY, 0.03 * DAY, THR, 8)
_EC = {}


def earliest(i, j, t_d, thr=THR, mr=8, W=6.0):
    key = (i, j, int(t_d * 50), int(thr))
    v = _EC.get(key)
    if v is not None:
        return v
    deps = np.arange(t_d, t_d + W, 0.05)
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, MINTOF * DAY, 8 * DAY, 0.03 * DAY, thr, mr)
    m = tof > 0
    out = None
    if m.any():
        arr = deps[m] + tof[m] / DAY; k = int(np.argmin(arr)); out = float(arr[k])
    _EC[key] = out
    return out


def reorder_small(cities, t0):
    """endpoint-constrained: keep cities[0] (entry) and cities[-1] (exit gateway); greedy-NN over the interior
    from t0, then append the exit. Returns the new order (same set) or None if it strands."""
    entry, exit_c = cities[0], cities[-1]
    interior = set(cities[1:-1])
    order = [entry]; last = entry; t = t0
    while interior:
        best = None
        for j in interior:
            a = earliest(last, j, t)
            if a is not None and (best is None or a < best[0]):
                best = (a, j)
        if best is None:
            return None
        t = best[0]; last = best[1]; order.append(last); interior.discard(last)
    a = earliest(last, exit_c, t)                                # close to the fixed exit gateway
    if a is None:
        return None
    order.append(exit_c)
    return order


def retime_full(order, bridge_pos, t0=0.0, mr=20, W=12.0):
    nl = len(order) - 1; times = np.empty(nl); tofs = np.empty(nl); t = t0
    for k in range(nl):
        thr = EXC if k in bridge_pos else THR
        key = (order[k], order[k + 1], int(t * 50), int(thr), mr)
        v = _EC.get(key)
        if v is None:
            deps = np.arange(t, t + W, 0.02)
            tof = ft.cheap_first_tof(OPAR[order[k]], OPAR[order[k + 1]], deps * DAY, MINTOF * DAY, 8 * DAY, 0.02 * DAY, thr, mr)
            m = tof > 0
            v = None if not m.any() else (lambda a: (float(deps[m][int(np.argmin(a))]), float(tof[m][int(np.argmin(a))] / DAY), float(a[int(np.argmin(a))])))(deps[m] + tof[m] / DAY)
            _EC[key] = v
        if v is None:
            return None, k
        times[k] = v[0]; tofs[k] = v[1]; t = v[2]
    return (times, tofs), nl


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; b_order = [int(c) for c in bank[2 * (N - 1):]]
    bt = np.array(bank[:N - 1]); bf = np.array(bank[N - 1:2 * (N - 1)])
    cur_mk = float(kt.fitness(bank)[0]); print(f"[E-743] bank {cur_mk:.2f}d", flush=True)
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)
    bridge_pos = set(k for k in range(N - 1)
                     if kt.compute_transfer(b_order[k], b_order[k + 1], float(bt[k]), float(bf[k])) > THR + 1e-6)
    # find small runs (maximal non-comp0)
    smalls = []; k = 0
    while k < N:
        if b_order[k] not in comp0:
            s = k
            while k < N and b_order[k] not in comp0:
                k += 1
            smalls.append((s, k))
        else:
            k += 1
    print(f"[E-743] smalls {[(e-s) for s,e in smalls]} entries {[round(float(bt[s]),1) for s,e in smalls]}", flush=True)
    t0 = time.time(); new_order = list(b_order); nimp = 0
    for (s, e) in smalls:
        cities = b_order[s:e]; t_entry = float(bt[s])
        ro = reorder_small(cities, t_entry)
        if ro is None or set(ro) != set(cities):
            print(f"[E-743] small@{s} reorder failed/stranded", flush=True); continue
        new_order[s:e] = ro; nimp += 1
        print(f"[E-743] small@{s} ({e-s}c) reordered [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-743] reordered {nimp}/{len(smalls)} smalls; faithful full-tour retime (mr=20)...", flush=True)
    res = retime_full(new_order, bridge_pos)
    if res[0] is None:
        print(f"[E-743] retime STRANDS at leg {res[1]} [{time.time()-t0:.0f}s]", flush=True); return
    ti, tf = res[0]; dv2 = list(ti) + list(tf) + [float(c) for c in new_order]
    fit = kt.fitness(dv2); mk = float(fit[0]); feas = max(float(x) for x in fit[1:]) <= 1e-6
    print(f"[E-743] NEW makespan {mk:.2f}d feas={feas} (gain {cur_mk-mk:+.2f}d) [{time.time()-t0:.0f}s]", flush=True)
    if feas and mk < cur_mk - 0.5:
        shutil.copy(f"{ROOT}/solutions/upload/large.json", f"{ROOT}/solutions/upload/large.json.bak_smalls")
        json.dump([{"decisionVector": [float(x) for x in dv2], "problem": "hard",
                    "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                  open(f"{ROOT}/solutions/upload/large.json", "w"))
        rt = float(kt.fitness(json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"])[0])
        print(f"[E-743] GUARD-BANKED large -> {rt:.2f}d; headroom vs next 1028.59 = {1028.59-rt:.0f}d; "
              f"r2=682 gap {rt-682:.0f}d. NOT submitted.", flush=True)
    else:
        print(f"[E-743] no bankable gain ({mk:.2f})", flush=True)


if __name__ == "__main__":
    main()
