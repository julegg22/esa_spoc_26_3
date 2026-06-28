"""E-747 — Ch2-LARGE targeted worst-leg destroy-repair LNS on comp0 (intermediate rank-2 lever).
Headroom decomp (E-742): comp0 = 93% of flight at 1.345 d/leg; 103 legs >2d = 40% of flight; median-floor ~452d.
comp0 pass-2 (segment or-opt) plateaued at 890.99 = local opt of a SMALL move. This applies a LARGER, TARGETED
move: destroy the R comp0 cities arriving via the worst legs, greedily REINSERT them at cheapest faithful positions
within their comp0 run (run endpoints fixed -> the 5 comp0<->small bridges preserved), then faithful full retime.
Accept iff makespan improves + feasible (exc<=5). Guard-banks; NOT a submission.
Usage: python ch2_giant_worst_leg_lns.py [rounds=300] [R=12]"""
import sys, json, time, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_lns_e742 as e                                    # earliest, retime_full, kt, OPAR, THR, EXC, _EC
ROOT = e.ROOT; kt = e.kt; THR = e.THR; EXC = e.EXC


def cheap_adj():
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); K = d["keys"]; F = np.isfinite(d["vals"])
    adj = {}
    for r, (i, j) in enumerate(K):
        if F[r].any():
            adj.setdefault(int(i), set()).add(int(j)); adj.setdefault(int(j), set()).add(int(i))
    return adj


def fit_of(order, bp):
    res = e.retime_full(order, bp)
    if res[0] is None:
        return None, None
    ti, tf = res[0]; dv = list(ti) + list(tf) + [float(c) for c in order]
    f = kt.fitness(dv); feas = max(float(x) for x in f[1:]) <= 1e-6
    return (float(f[0]) if feas else None), (tf, dv)


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    R = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051; order = [int(c) for c in bank[2 * (N - 1):]]
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)
    adj = cheap_adj()

    def bridges(o):                                               # structural comp0<->small crossings (the 5 exc legs)
        return set(k for k in range(N - 1) if (o[k] in comp0) != (o[k + 1] in comp0))

    bp = bridges(order)
    best, pack = fit_of(order, bp)
    if best is None:
        print("[E-747] baseline infeasible/strands", flush=True); return
    cur_tf = pack[0]
    print(f"[E-747] baseline {best:.2f}d, {len(bp)} bridges, R={R}, rounds={rounds}", flush=True)
    rng = np.random.RandomState(1); t0 = time.time(); naccept = 0

    for it in range(rounds):
        # comp0 runs (so we keep run endpoints fixed)
        runs = []; k = 0
        while k < N:
            if order[k] in comp0:
                s = k
                while k < N and order[k] in comp0:
                    k += 1
                runs.append((s, k))
            else:
                k += 1
        run_of = {}
        for (s, en) in runs:
            for p in range(s, en):
                run_of[p] = (s, en)
        # worst comp0-internal legs -> remove their ARRIVING city (interior only), R of them, jittered
        cand = sorted(((cur_tf[k], k) for k in range(N - 1)
                       if order[k] in comp0 and order[k + 1] in comp0 and k not in bp), reverse=True)
        topcut = cand[:max(R * 4, 40)]
        rng.shuffle(topcut)
        remove = []
        for _, k in topcut:
            p = k + 1
            if p in run_of:
                s, en = run_of[p]
                if s < p < en - 1:
                    remove.append(p)
            if len(remove) >= R:
                break
        if not remove:
            continue
        rem = set(remove); rem_cities = [order[p] for p in remove]
        newo = [order[p] for p in range(N) if p not in rem]
        # greedy cheapest-insertion within comp0 interior, near a cheap neighbour
        ok = True
        for c in rem_cities:
            nbrs = adj.get(c, set())
            cp = [q + 1 for q in range(len(newo) - 1)
                  if newo[q] in nbrs and newo[q] in comp0 and newo[q + 1] in comp0]
            if not cp:
                cp = [q + 1 for q in range(len(newo) - 1) if newo[q] in comp0 and newo[q + 1] in comp0][:50]
            bestpos = None; bestc = 1e9
            for q in cp:
                ra = e.earliest(newo[q - 1], c, 0.0, THR); rc = e.earliest(c, newo[q], 0.0, THR)
                if ra is None or rc is None:
                    continue
                cc = ra[1] + rc[1]
                if cc < bestc:
                    bestc = cc; bestpos = q
            if bestpos is None:
                ok = False; break
            newo.insert(bestpos, c)
        if not ok or len(newo) != N or set(newo) != set(order):
            continue
        nbp = bridges(newo)
        mk, pack2 = fit_of(newo, nbp)
        if mk is not None and mk < best - 0.1:
            best = mk; order = newo; bp = nbp; cur_tf = pack2[0]; naccept += 1
            shutil.copy(f"{ROOT}/solutions/upload/large.json", f"{ROOT}/solutions/upload/large.json.bak_worstleg")
            json.dump([{"decisionVector": [float(x) for x in pack2[1]], "problem": "hard",
                        "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
                      open(f"{ROOT}/solutions/upload/large.json", "w"))
            print(f"[E-747] it{it}: NEW BEST {mk:.2f}d GUARD-BANKED (acc{naccept}) [{time.time()-t0:.0f}s]", flush=True)
        elif it % 15 == 0:
            print(f"[E-747] it{it}: try {mk if mk else 'infeas'} (best {best:.2f}) [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-747] DONE {naccept} accepts, best {best:.2f}d [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
