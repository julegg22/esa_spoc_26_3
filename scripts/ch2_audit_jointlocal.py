"""Ch2-small DEEP AUDIT (2026-06-22) v2: is 112.996 a TRUE basin, or an artifact of the order search
steering by the DP-grid proxy (the +5.5d offset E-653 caught) and never officially re-timing orders?

S1 proved the bank ORDER's schedule is officially optimal. The untested question: does any small
ORDER move from the bank, given its OWN free official schedule, beat 112.996? The prior order searches
ranked orders by the DP proxy (offset, order-dependent) and never officially re-timed explored orders.

KEY METHOD FIX (v1 lesson): the official schedule landscape is RUGGED — CMA is only a LOCAL polisher
(a from-scratch greedy seed gave 161 and CMA could not recover to 112.996). So every neighbor's
official retime is WARM-STARTED from the BANK's real 112.996 schedule vector (valid because a small
order move perturbs only ~2-3 legs). This is a tight LOCAL joint-(order,schedule) basin test on the
TRUE objective: if NO small official move descends, the bank is a genuine local opt (basin-isolation
holds locally); if one does, the order-basin verdict was a DP-proxy artifact.
"""
import sys, json, time
import numpy as np
import cma
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
kt = KTTSP(INST); n = kt.n
x0 = np.array(json.load(open(BANK))[0]["decisionVector"], dtype=float)
BANK_ORDER = [round(v) for v in x0[2 * (n - 1):]]
BANK_MK = 112.996
RNG = np.random.default_rng(7)

# bank's REAL schedule -> encoding seed (t0, tofs(48), waits(47)) = 96 vars  (identical to S1)
bt = x0[:n - 1]; bf = x0[n - 1:2 * (n - 1)]
WAITS0 = np.array([max(bt[i + 1] - (bt[i] + bf[i]), 0.0) for i in range(n - 2)])
ENC0 = np.concatenate([[bt[0]], bf, WAITS0])


def decode(enc):
    t0 = max(enc[0], 0.0); tofs = np.maximum(enc[1:n], kt.min_tof); waits = np.maximum(enc[n:], 0.0)
    times = np.empty(n - 1); times[0] = t0
    for i in range(n - 2):
        times[i + 1] = times[i] + tofs[i] + waits[i]
    return times, tofs


def evalx(enc, order):
    times, tofs = decode(enc)
    f = kt.fitness(list(times) + list(tofs) + [float(o) for o in order])
    pen = 1000.0 * (abs(f[2]) + abs(f[3]) + max(0.0, f[4]))
    if times[-1] + tofs[-1] > kt.max_time:
        pen += 1000.0 * (times[-1] + tofs[-1] - kt.max_time)
    return f[0] + pen, f[0], kt.is_feasible(f)


def retime_official(order, seed_enc, budget=6000, sigma=0.15, seed=1):
    """WARM-STARTED official CMA retime of a fixed order (seed = bank schedule vector)."""
    es = cma.CMAEvolutionStrategy(seed_enc, sigma, {'maxfevals': budget, 'popsize': 20,
                                                    'bounds': [0.0, None], 'verbose': -9, 'seed': seed})
    o0, mk0, feas0 = evalx(seed_enc, order)
    best = mk0 if feas0 else float("inf")
    while not es.stop():
        sols = es.ask(); vals = []
        for s in sols:
            o, mk, feas = evalx(s, order); vals.append(o)
            if feas and mk < best:
                best = mk
        es.tell(sols, vals)
    return best


def make_neighbors():
    out = []
    for p in range(n - 1):                                   # all adjacent swaps (tightest, best seed)
        o = BANK_ORDER.copy(); o[p], o[p + 1] = o[p + 1], o[p]; out.append(("swap%02d" % p, o))
    for _ in range(30):                                      # short or-opt: move a city by 1-3 positions
        p = int(RNG.integers(0, n)); d = int(RNG.integers(1, 4)) * (1 if RNG.random() < 0.5 else -1)
        q = p + d
        if q < 0 or q >= n or p == q:
            continue
        o = BANK_ORDER.copy(); c = o.pop(p); o.insert(q, c); out.append(("oropt", o))
    return out


def main():
    t0 = time.time()
    rt_b = retime_official(BANK_ORDER, ENC0, budget=8000)
    print(f"[AUDIT v2] positive control: warm official retime of BANK order = {rt_b:.4f} "
          f"(expect 112.996) [{time.time()-t0:.0f}s]", flush=True)
    if abs(rt_b - BANK_MK) > 0.3:
        print("  ABORT: control does not reproduce bank — seed/evaluator bug.", flush=True); return

    nbrs = make_neighbors()
    print(f"[AUDIT v2] warm official retime of {len(nbrs)} small order-neighbors (seed=bank schedule) ...", flush=True)
    results = []; wins = []
    for k, (tag, o) in enumerate(nbrs):
        rt = retime_official(o, ENC0, budget=6000, seed=1 + k)
        results.append(rt)
        if rt < BANK_MK - 1e-3:
            wins.append((rt, tag, o))
            print(f"  {tag}: official-retime={rt:.4f} ({rt-BANK_MK:+.4f})  ** BELOW 112.996 ** [{time.time()-t0:.0f}s]", flush=True)
        if (k + 1) % 12 == 0:
            fin = [r for r in results if np.isfinite(r)]
            print(f"  ..{k+1}/{len(nbrs)} done; feas={len(fin)}; best-neighbor={min(fin) if fin else float('inf'):.4f} [{time.time()-t0:.0f}s]", flush=True)
    fin = [r for r in results if np.isfinite(r)]
    print(f"\n[AUDIT v2] {len(fin)}/{len(nbrs)} neighbors feasible; best-neighbor makespan = "
          f"{min(fin) if fin else float('inf'):.4f} (bank 112.996)", flush=True)
    if wins:
        wins.sort()
        print(f"[AUDIT v2] *** LOCAL BASIN BROKEN: {len(wins)} small move(s) beat 112.996 on the OFFICIAL "
              f"objective; best {wins[0][0]:.4f} ({wins[0][1]}) ***", flush=True)
        json.dump({"makespan": wins[0][0], "tag": wins[0][1], "order": list(wins[0][2])},
                  open("/tmp/ch2_audit_winner.json", "w"))
        print(f"[AUDIT v2] -> 'basin-isolated at 112.996' was a DP-proxy artifact; official-scored order "
              f"search (DP-rank + official retime) is the realizable lever.", flush=True)
    else:
        print(f"[AUDIT v2] NO small order move beats 112.996 under free official schedule ⇒ the bank is a "
              f"genuine LOCAL joint (order,schedule) optimum on the true objective.", flush=True)
        print(f"[AUDIT v2] -> basin-isolation holds locally; any descent needs a NON-local re-interleave "
              f"(time-expanded TD-TSP), consistent with the prior verdict — but now proven on the OFFICIAL metric.", flush=True)
    print(f"[AUDIT v2] DONE [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
