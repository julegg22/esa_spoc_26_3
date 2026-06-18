"""Ch2-small FAITHFUL order search: grid-DP-mk was shown to be an unfaithful proxy
(it undervalues orders with continuous-scheduling headroom, like the bank). So evaluate
each candidate ORDER by the OFFICIAL evaluator via a short warm-started CMA schedule polish,
starting from the bank order's headroom basin. Perturb order (2-swap / or-opt) → CMA-refine
schedule on kt.fitness → SA-accept → guard-bank if official mk < 112.996.

One process = one chain (pass seed). Warm-starts each refine from the incumbent schedule, so
the CMA budget can be small. Instrumented: per-iter log, best tracking, guard-bank (atomic +
official re-validate). Usage: python ch2_faithful_order_search.py [seed=0] [cma_budget=6000] [wall_h=48]
"""
import sys, json, time, shutil, random, os
import numpy as np
import cma
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
kt = KTTSP(INST); n = kt.n


def decode(enc):
    t0 = enc[0]; tofs = np.maximum(enc[1:n], kt.min_tof); waits = np.maximum(enc[n:], 0.0)
    times = np.empty(n - 1); times[0] = max(t0, 0.0)
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


def refine(order, enc0, budget):
    # cheap pre-screen: refining a perturbed order costs ~budget*30ms (slow Lambert on
    # infeasible legs). Only pay it when the warm-start is already near-feasible/near-bank.
    obj0, mk0, feas0 = evalx(enc0, order)
    if (not feas0) or mk0 > 125.0:
        return (mk0 if feas0 else 1e9), enc0.copy()
    es = cma.CMAEvolutionStrategy(enc0, 0.05, {
        'maxfevals': budget, 'popsize': 16, 'bounds': [0.0, None], 'verbose': -9, 'seed': 1})
    best_mk = mk0 if feas0 else 1e9; best_enc = enc0.copy()
    while not es.stop():
        sols = es.ask(); vals = []
        for s in sols:
            o, mk, feas = evalx(s, order); vals.append(o)
            if feas and mk < best_mk:
                best_mk = mk; best_enc = s.copy()
        es.tell(sols, vals)
    return best_mk, best_enc


def perturb(order, rng):
    o = order[:]
    if rng.random() < 0.5:                       # 2-swap
        a, b = rng.sample(range(n), 2); o[a], o[b] = o[b], o[a]
    else:                                        # or-opt: move a short segment
        L = rng.randint(1, 3); i = rng.randint(0, n - L); seg = o[i:i + L]; del o[i:i + L]
        j = rng.randint(0, len(o)); o[j:j] = seg
    return o


def guard_bank(order, enc, bank_mk, log):
    times, tofs = decode(enc)
    dv = [float(x) for x in (list(times) + list(tofs) + [float(p) for p in order])]
    f = kt.fitness(dv)
    if kt.is_feasible(f) and f[0] < bank_mk - 1e-4:
        cur = json.load(open(BANK)); cur_mk = float(kt.fitness(cur[0]['decisionVector'])[0])
        if f[0] < cur_mk - 1e-4:
            shutil.copy(BANK, BANK + ".bak.faithful")
            tmp = BANK + ".tmp"
            json.dump([{"decisionVector": dv, "problem": "small"}], open(tmp, "w"))
            chk = float(kt.fitness(json.load(open(tmp))[0]['decisionVector'])[0])
            if chk < cur_mk - 1e-4:
                os.replace(tmp, BANK); log(f"BANKED {chk:.4f} (was {cur_mk:.4f})"); return chk
            os.remove(tmp)
    return None


def main(seed=0, budget=6000, wall_h=48.0):
    rng = random.Random(seed * 7919 + 13)
    log = lambda m: print(f"[s{seed}] {m}", flush=True)
    x0 = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    order = [round(v) for v in x0[2 * (n - 1):]]
    bank_mk = float(kt.fitness(list(x0))[0])
    waits0 = np.array([x0[:n - 1][i + 1] - (x0[:n - 1][i] + x0[n - 1:2 * (n - 1)][i]) for i in range(n - 2)])
    enc = np.concatenate([[x0[0]], x0[n - 1:2 * (n - 1)], np.maximum(waits0, 0)])
    # control
    _, mk0, feas0 = evalx(enc, order)
    log(f"control: bank order official mk={mk0:.4f} feas={feas0} (expect {bank_mk:.4f})")
    if not feas0 or abs(mk0 - bank_mk) > 0.5:
        log("ABORT control"); return
    cur_mk = mk0; cur_order = order; cur_enc = enc.copy()
    best_mk = mk0; t0 = time.time(); it = 0; nacc = 0; Temp = 0.5
    while time.time() - t0 < wall_h * 3600:
        it += 1
        no = perturb(cur_order, rng)
        mk, enc2 = refine(no, cur_enc, budget)
        if mk < cur_mk - 1e-9 or rng.random() < np.exp(-(mk - cur_mk) / max(Temp, 1e-3)):
            cur_mk = mk; cur_order = no; cur_enc = enc2; nacc += 1
        if mk < best_mk - 1e-4:
            best_mk = mk
            log(f"NEW BEST official mk={mk:.4f} ({mk-bank_mk:+.4f}) it={it}")
            b = guard_bank(no, enc2, bank_mk, log)
        Temp *= 0.999
        if it % 10 == 0:
            log(f"it={it} cur={cur_mk:.4f} best={best_mk:.4f} acc={nacc} T={Temp:.3f} "
                f"[{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        # ONE process spawns 4 chains internally (avoids sandbox direct-python death
        # AND the micromamba env-lock serialization of 4 separate `micromamba run`s).
        import multiprocessing as mp
        bg = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
        wh = float(sys.argv[3]) if len(sys.argv) > 3 else 48.0
        procs = [mp.Process(target=main, args=(s, bg, wh)) for s in range(4)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
    else:
        sd = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        bg = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
        wh = float(sys.argv[3]) if len(sys.argv) > 3 else 48.0
        main(sd, bg, wh)
