"""E-748 — Ch2-LARGE exact-clock worst-leg repair (the CORRECT version of E-747). E-747's perturb-then-greedy-
retime produced 0 feasible (epoch-shift fragility, C-036). The fix: re-solve a WINDOW of comp0 cities around each
worst leg with an EXACT-CLOCK beam that carries the real running clock from the window's true entry epoch (the
method that works, C-034) — entry & exit cities fixed (run-internal, bridges untouched). If the window's exit
arrival beats the bank's, splice + faithful full retime + accept iff makespan improves & feasible.
Usage: python ch2_giant_worstleg_beam_repair.py [rounds=400] [M=14] [Ws=60]"""
import sys, json, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_lns_e742 as e                                    # earliest, retime_full, kt, THR, EXC, ROOT
ROOT = e.ROOT; kt = e.kt; THR = e.THR


def window_beam(entry, interior, exit_c, t_entry, Ws):
    """exact-clock beam over a window: from entry@t_entry, visit all `interior`, end at exit_c; min exit arrival."""
    beam = [(frozenset(), entry, t_entry, [entry])]
    for _ in range(len(interior)):
        succ = []
        for vis, last, t, path in beam:
            for j in interior:
                if j in vis:
                    continue
                r = e.earliest(last, j, t, THR)
                if r is not None:
                    succ.append((vis | {j}, j, r[2], path + [j]))
        if not succ:
            return None
        succ.sort(key=lambda s: s[2])
        beam = succ[:Ws]
    best = None
    for vis, last, t, path in beam:
        r = e.earliest(last, exit_c, t, THR)
        if r is not None and (best is None or r[2] < best[0]):
            best = (r[2], path + [exit_c])
    return best


def fit_of(order, bp):
    res = e.retime_full(order, bp)
    if res[0] is None:
        return None, None
    ti, tf = res[0]; dv = list(ti) + list(tf) + [float(c) for c in order]
    f = kt.fitness(dv); feas = max(float(x) for x in f[1:]) <= 1e-6
    return (float(f[0]) if feas else None), dv


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    M = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    Ws = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; order = [int(c) for c in bank[2 * (N - 1):]]
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)

    def bridges(o):
        return set(k for k in range(N - 1) if (o[k] in comp0) != (o[k + 1] in comp0))

    bp = bridges(order)
    best, _ = fit_of(order, bp)
    if best is None:
        print("[E-748] baseline infeasible"); return
    print(f"[E-748] baseline {best:.2f}d, M={M}, Ws={Ws}", flush=True)
    t0 = time.time(); naccept = 0

    for it in range(rounds):
        res = e.retime_full(order, bp)
        if res[0] is None:
            break
        ti, tf = res[0]
        arr = np.array(ti) + np.array(tf)                         # arrival epoch per leg
        # comp0 runs (windows must stay inside one run; entry/exit fixed)
        runs = []; k = 0
        while k < N:
            if order[k] in comp0:
                s = k
                while k < N and order[k] in comp0:
                    k += 1
                runs.append((s, k))
            else:
                k += 1
        # worst comp0-internal legs, jittered, that admit an M-window inside a run
        cand = sorted(((tf[kk], kk) for kk in range(N - 1)
                       if order[kk] in comp0 and order[kk + 1] in comp0 and kk not in bp), reverse=True)
        improved = False
        for _, kk in cand[: it % 40 + 8]:                         # rotate through worst legs across rounds
            run = next((r for r in runs if r[0] <= kk < r[1] - 1), None)
            if run is None:
                continue
            a = max(run[0], kk - M // 2); b = min(run[1] - 1, a + M)
            if b - a < 4:
                continue
            entry = order[a]; exit_c = order[b]; interior = [order[p] for p in range(a + 1, b)]
            t_entry = float(ti[a]) if a == 0 else float(arr[a - 1])  # epoch we depart `entry`
            orig_exit_arr = float(arr[b - 1])                     # bank arrival at exit_c
            wb = window_beam(entry, interior, exit_c, t_entry, Ws)
            if wb is None or wb[0] >= orig_exit_arr - 0.05:
                continue
            neworder = order[:a] + wb[1] + order[b + 1:]
            if len(neworder) != N or set(neworder) != set(order):
                continue
            nbp = bridges(neworder)
            mk, dv = fit_of(neworder, nbp)
            if mk is not None and mk < best - 0.1:
                best = mk; order = neworder; bp = nbp; naccept += 1; improved = True
                shutil.copy(f"{ROOT}/solutions/upload/large.json", f"{ROOT}/solutions/upload/large.json.bak_wlbeam")
                json.dump([{"decisionVector": [float(x) for x in dv], "problem": "hard",
                            "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                          open(f"{ROOT}/solutions/upload/large.json", "w"))
                print(f"[E-748] it{it} leg{kk}: NEW BEST {mk:.2f}d GUARD-BANKED (acc{naccept}) [{time.time()-t0:.0f}s]", flush=True)
                break
        if not improved and it % 10 == 0:
            print(f"[E-748] it{it}: no improve (best {best:.2f}) [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-748] DONE {naccept} accepts, best {best:.2f}d [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
