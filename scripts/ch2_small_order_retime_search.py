"""E-755 — Ch2-small order-search with FAITHFUL RE-TIME (the proper version; E-753 joint-SA jittered epochs
randomly so good orders were rejected on bad timing). We're at 112.996 (rank 6) while a cluster sits at ~111.76
(ranks 4-5) and rank-3 is 110.88. Standard-method gap ~1.2-2.1d. This: 2-opt + or-opt moves on the ORDER, then
GREEDY-EARLIEST faithful re-time (cheap THR, exception EXC fallback, fine 0.005d), score official kt.fitness,
accept iff kt.is_feasible AND makespan improves (SA temperature to escape the bank's local opt). Guard-bank any
feasible <112.996; verify with kt.is_feasible + re-derivation (the 0.039-exploit lesson).
Usage: python ch2_small_order_retime_search.py [iters=40000]"""
import sys, json, math, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch2_kttsp import KTTSP
import ch2_fast_transfer as ft
ROOT = "/home/julian/Projects/esa_spoc_26_3"
kt = KTTSP(f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OPAR = kt.opar.astype(np.float64); DAY = 86400.0; THR = kt.dv_thr; EXC = kt.dv_exc; MR = kt.max_revs; N = 49
ft.cheap_first_tof(OPAR[0], OPAR[1], np.array([0.0, DAY]), kt.min_tof * DAY, 8 * DAY, 0.005 * DAY, THR, MR)
_C = {}


def leg(i, j, t, thr):
    key = (i, j, int(t * 200), int(thr))
    v = _C.get(key)
    if v is not None:
        return v
    deps = np.arange(t, t + 6.0, 0.005)
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], deps * DAY, kt.min_tof * DAY, 8 * DAY, 0.005 * DAY, thr, MR)
    m = tof > 0
    out = None if not m.any() else (lambda a: (float(deps[m][np.argmin(a)]), float(tof[m][np.argmin(a)] / DAY), float(a.min())))(deps[m] + tof[m] / DAY)
    _C[key] = out
    return out


def retime(order):
    """greedy-earliest: cheap if feasible else exception; return (times,tofs,nexc) or None."""
    t = 0.0; tm = np.empty(N - 1); tf = np.empty(N - 1); nexc = 0
    for k in range(N - 1):
        r = leg(order[k], order[k + 1], t, THR)
        if r is None:
            r = leg(order[k], order[k + 1], t, EXC)
            if r is None:
                return None
            nexc += 1
            if nexc > 5:
                return None
        tm[k] = r[0]; tf[k] = r[1]; t = r[2]
    return tm, tf, nexc


def score(order):
    r = retime(order)
    if r is None:
        return None, None
    tm, tf, nexc = r
    dv = list(tm) + list(tf) + [float(c) for c in order]
    f = kt.fitness(dv)
    return (float(f[0]) if kt.is_feasible(f) else None), dv


def main():
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    bank = json.load(open(f"{ROOT}/solutions/upload/small.json"))[0]["decisionVector"]
    order = [int(c) for c in bank[2 * (N - 1):]]
    cur, _ = score(order)
    print(f"[E-755] bank order retimed -> {cur:.3f}d (target <112.996; rank5 111.76, rank3 110.88)", flush=True)
    best = cur; best_order = list(order); cur_order = list(order)
    rng = np.random.RandomState(3); t0 = time.time(); T = 0.6; nacc = 0
    for it in range(iters):
        no = list(cur_order); m = rng.randint(3)
        if m == 0:                                              # 2-opt: reverse interior segment
            a, b = sorted(rng.randint(1, N, 2))
            no[a:b + 1] = no[a:b + 1][::-1]
        elif m == 1:                                            # or-opt: relocate one city
            i = rng.randint(1, N); c = no.pop(i); j = rng.randint(1, N - 1); no.insert(j, c)
        else:                                                  # or-opt-2: relocate a pair
            i = rng.randint(1, N - 2); seg = no[i:i + 2]; del no[i:i + 2]; j = rng.randint(1, N - 2); no[j:j] = seg
        mk, dv = score(no)
        if mk is not None and (mk < cur or rng.random() < math.exp(-(mk - cur) / max(T, 1e-3))):
            cur_order = no; cur = mk; nacc += 1
            if mk < best - 1e-4:
                best = mk; best_order = list(no)
                if mk < 112.99:
                    print(f"[E-755] it{it}: NEW BEST {mk:.3f}d (acc{nacc}) [{time.time()-t0:.0f}s]", flush=True)
        T *= 0.99997
        if it % 4000 == 0:
            print(f"[E-755] it{it}: cur {cur:.3f} best {best:.3f} T={T:.3f} [{time.time()-t0:.0f}s]", flush=True)
            if T < 0.03:
                T = 0.5; cur_order = list(best_order); cur = best
    print(f"[E-755] DONE best {best:.3f}d (bank 112.996) [{time.time()-t0:.0f}s]", flush=True)
    if best < 112.996 - 1e-3:
        mk, dv = score(best_order)
        if mk is not None and kt.is_feasible(kt.fitness(dv)):
            nexc = sum(1 for k in range(N - 1) if kt.compute_transfer(best_order[k], best_order[k + 1], dv[k], dv[N - 1 + k]) > THR + 1e-6)
            print(f"[E-755] VERIFY: {mk:.3f}d feasible, exc={nexc}, cities={sorted(best_order)==list(range(N))}", flush=True)
            if nexc <= 5 and sorted(best_order) == list(range(N)):
                shutil.copy(f"{ROOT}/solutions/upload/small.json", f"{ROOT}/solutions/upload/small.json.bak_retime")
                json.dump([{"decisionVector": [float(x) for x in dv], "problem": "small",
                            "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                          open(f"{ROOT}/solutions/upload/small.json", "w"))
                print(f"[E-755] *** GUARD-BANKED small -> {mk:.3f}d (was 112.996) -> ESCALATE re-submit", flush=True)


if __name__ == "__main__":
    main()
