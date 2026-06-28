"""E-748b — aggressive multi-window exact-clock worst-leg repair (E-748 banked 890.99->879.53 but found only 1
accept with a fixed window M=14). This version, per worst comp0 leg, tries SEVERAL window sizes M and beam widths,
keeps the first full-tour-improving feasible splice, and sweeps ALL worst legs each round (no rotation cap). Same
safe core: exact-clock beam from the real entry epoch, comp0 run endpoints fixed (5 bridges preserved), faithful
full retime, accept iff makespan improves & feasible. Guard-banks; NOT a submission.
Usage: python ch2_giant_worstleg_repair_v2.py [rounds=2000]"""
import sys, json, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_lns_e742 as e
ROOT = e.ROOT; kt = e.kt; THR = e.THR
MS = [12, 22]                                                     # window sizes tried per worst leg (light: fast rounds)
WS = 45                                                            # in-window beam width


def window_beam(entry, interior, exit_c, t_entry, Ws=WS):
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
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; order = [int(c) for c in bank[2 * (N - 1):]]
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)

    def bridges(o):
        return set(k for k in range(N - 1) if (o[k] in comp0) != (o[k + 1] in comp0))

    bp = bridges(order)
    best, _ = fit_of(order, bp)
    print(f"[E-748b] baseline {best:.2f}d; MS={MS} WS={WS}", flush=True)
    t0 = time.time(); nacc = 0
    for it in range(rounds):
        res = e.retime_full(order, bp)
        if res[0] is None:
            break
        ti, tf = res[0]; arr = np.array(ti) + np.array(tf)
        runs = []; k = 0
        while k < N:
            if order[k] in comp0:
                s = k
                while k < N and order[k] in comp0:
                    k += 1
                runs.append((s, k))
            else:
                k += 1
        cand = sorted(((tf[kk], kk) for kk in range(N - 1)
                       if order[kk] in comp0 and order[kk + 1] in comp0 and kk not in bp), reverse=True)
        improved = False
        for _, kk in cand[:18]:                                   # the worst comp0 legs this round (light)
            run = next((r for r in runs if r[0] <= kk < r[1] - 1), None)
            if run is None:
                continue
            for M in MS:
                a = max(run[0], kk - M // 2); b = min(run[1] - 1, a + M)
                if b - a < 4:
                    continue
                interior = [order[p] for p in range(a + 1, b)]
                t_entry = float(ti[a]) if a == 0 else float(arr[a - 1])
                orig = float(arr[b - 1])
                wb = window_beam(order[a], interior, order[b], t_entry)
                if wb is None or wb[0] >= orig - 0.05:
                    continue
                neworder = order[:a] + wb[1] + order[b + 1:]
                if len(neworder) != N or set(neworder) != set(order):
                    continue
                nbp = bridges(neworder)
                mk, dv = fit_of(neworder, nbp)
                if mk is not None and mk < best - 0.05:
                    best = mk; order = neworder; bp = nbp; nacc += 1; improved = True
                    shutil.copy(f"{ROOT}/solutions/upload/large.json", f"{ROOT}/solutions/upload/large.json.bak_wlv2")
                    json.dump([{"decisionVector": [float(x) for x in dv], "problem": "hard",
                                "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                              open(f"{ROOT}/solutions/upload/large.json", "w"))
                    print(f"[E-748b] it{it} leg{kk} M{M}: NEW BEST {mk:.2f}d (acc{nacc}) [{time.time()-t0:.0f}s]", flush=True)
                    break
            if improved:
                break
        if not improved and it % 8 == 0:
            print(f"[E-748b] it{it}: no improve (best {best:.2f}) [{time.time()-t0:.0f}s]", flush=True)
        if not improved and it > 30 and nacc == 0:
            print(f"[E-748b] no accepts in 30 rounds -> plateaued at {best:.2f}", flush=True); break
    print(f"[E-748b] DONE {nacc} accepts, best {best:.2f}d [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
