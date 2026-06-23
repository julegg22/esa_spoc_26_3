"""E-703 pivot test — SA over orders minimizing the FAST table-DP walk, then CONTINUOUS-retime the best
orders officially. Tests whether table-DP search finds orders that retime below the bank's 112.996.

Prior order searches compared table-DP candidates to the OFFICIAL bank value (the +5.5d apples-to-oranges
bug). Here: minimize table-DP (fast walk, ~ms), keep the best distinct orders, then S1-style continuous
official CMA-retime each (seeded from its walk schedule). Bank candidate if official feasible <112.996.
Usage: python ch2_walk_sa.py [iters=40000] [seed=1]"""
import sys, json, time
import numpy as np
import cma
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch2_kttsp import KTTSP
from ch2_faithful_walk import walk, n, Q, T
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
kt = KTTSP(INST)
BANK_MK = 112.996


def tabledp(order):
    _, _, mk, ok, _ = walk(order)
    return mk if ok else 1e9


def retime_official(order, seed_times, seed_tofs, budget=8000, sigma=0.15):
    waits0 = np.array([max(seed_times[i + 1] - (seed_times[i] + seed_tofs[i]), 0.0) for i in range(n - 2)])
    enc0 = np.concatenate([[seed_times[0]], seed_tofs, waits0])

    def decode(enc):
        t0 = max(enc[0], 0.0); tofs = np.maximum(enc[1:n], kt.min_tof); waits = np.maximum(enc[n:], 0.0)
        times = np.empty(n - 1); times[0] = t0
        for i in range(n - 2):
            times[i + 1] = times[i] + tofs[i] + waits[i]
        return times, tofs

    def ev(enc):
        times, tofs = decode(enc)
        f = kt.fitness(list(times) + list(tofs) + [float(o) for o in order])
        pen = 1000.0 * (abs(f[2]) + abs(f[3]) + max(0.0, f[4]))
        if times[-1] + tofs[-1] > kt.max_time:
            pen += 1000.0 * (times[-1] + tofs[-1] - kt.max_time)
        return f[0] + pen, f[0], kt.is_feasible(f)

    o0, mk0, fe0 = ev(enc0)
    es = cma.CMAEvolutionStrategy(enc0, sigma, {'maxfevals': budget, 'popsize': 18,
                                                'bounds': [0.0, None], 'verbose': -9, 'seed': 1})
    best = mk0 if fe0 else 1e9
    while not es.stop():
        sols = es.ask(); vals = []
        for s in sols:
            o, mk, fe = ev(s); vals.append(o)
            if fe and mk < best:
                best = mk
        es.tell(sols, vals)
    return best


def main(iters=40000, seed=1):
    rng = np.random.default_rng(seed)
    x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    cur = [round(v) for v in x[2 * (n - 1):]]
    cur_mk = tabledp(cur)
    print(f"[WALK-SA] bank order table-DP={cur_mk:.4f}d (official 112.996). SA {iters} iters ...", flush=True)
    best = cur[:]; best_mk = cur_mk; pool = {tuple(cur): cur_mk}
    Temp = 2.0; t0 = time.time()
    for it in range(iters):
        a, b = sorted(rng.integers(0, n, 2))
        if b - a < 1:
            continue
        cand = cur[:]
        if rng.random() < 0.5:
            cand[a:b + 1] = cand[a:b + 1][::-1]            # 2-opt
        else:
            c = cand.pop(a); cand.insert(b, c)             # or-opt
        mk = tabledp(cand)
        if mk < cur_mk or rng.random() < np.exp(-(mk - cur_mk) / Temp):
            cur, cur_mk = cand, mk
            if mk < best_mk - 1e-6:
                best, best_mk = cand[:], mk
                pool[tuple(cand)] = mk
            elif mk < cur_mk + 3:
                pool[tuple(cand)] = mk
        Temp = max(0.2, Temp * 0.99995)
        if (it + 1) % 5000 == 0:
            print(f"  it {it+1}: cur={cur_mk:.3f} best={best_mk:.3f} T={Temp:.2f} pool={len(pool)} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[WALK-SA] best table-DP order = {best_mk:.4f}d (bank table-DP 118.53). retiming top orders ...", flush=True)
    top = sorted(pool.items(), key=lambda kv: kv[1])[:8]
    win = None
    for order_t, mk_dp in top:
        order = list(order_t); ti, tf, _, ok, _ = walk(order)
        if not ok:
            continue
        rt = retime_official(order, ti, tf)
        flag = "  ** < 112.996 **" if rt < BANK_MK - 1e-3 else ""
        print(f"  table-DP={mk_dp:.3f} -> official-retime={rt:.4f} ({rt-BANK_MK:+.3f}){flag} [{time.time()-t0:.0f}s]", flush=True)
        if rt < BANK_MK - 1e-3 and (win is None or rt < win[0]):
            win = (rt, order)
    if win:
        print(f"\n[WALK-SA] *** WIN: official {win[0]:.4f}d < 112.996 (R4 111.76 R3 110.88) — guard-bank candidate ***", flush=True)
        json.dump({"makespan": win[0], "order": win[1]}, open("/tmp/ch2_walk_sa_winner.json", "w"))
    else:
        print(f"\n[WALK-SA] no order retimes below 112.996. Correlation check: best table-DP {best_mk:.3f} vs bank 118.53 "
              f"-> if best_tabledp << 118.53 but retimes >=112.996, table-DP and official are decoupled (Ch2-small blocked for fast methods).", flush=True)


if __name__ == "__main__":
    it = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    main(it, sd)
