"""Stage-2 of the Ch2-small joint search: CMA-refine the DP-space candidate ORDERS
(dumped by e617-dpspace) on the OFFICIAL evaluator, warm-started from each order's DP
schedule, to remove the ~5.5d table-discretization offset. Guard-bank if official mk<112.996.

Reuses S1's validated encoding (decode/evalx reproduce bank=112.996) but with the
candidate's PERM fixed instead of the bank perm. Includes a positive control: refining the
BANK order must reproduce ~112.996. Guard-bank = backup→write→official re-validate.
Usage: python ch2_refine_dpspace_orders.py [topk=8] [budget_per_order=40000]
"""
import sys, json, time, shutil
import numpy as np
import cma
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
CAND = "/tmp/ch2_e617_dpspace_cand.jsonl"
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


def enc_from_schedule(times, tofs):
    times = np.asarray(times, float); tofs = np.asarray(tofs, float)
    waits = np.array([times[i + 1] - (times[i] + tofs[i]) for i in range(n - 2)])
    return np.concatenate([[times[0]], tofs, np.maximum(waits, 0)])


def refine(order, enc0, budget, label):
    obj0, mk0, feas0 = evalx(enc0, order)
    print(f"  [{label}] warm-start official mk={mk0:.4f} feas={feas0}", flush=True)
    es = cma.CMAEvolutionStrategy(enc0, 0.2, {
        'maxfevals': budget, 'popsize': 24, 'bounds': [0.0, None], 'verbose': -9, 'seed': 1})
    best_mk = mk0 if feas0 else 1e9; best_enc = enc0.copy(); ne = 0; t0 = time.time()
    while not es.stop():
        sols = es.ask(); vals = []
        for s in sols:
            o, mk, feas = evalx(s, order); vals.append(o); ne += 1
            if feas and mk < best_mk:
                best_mk = mk; best_enc = s.copy()
        es.tell(sols, vals)
    print(f"  [{label}] refined official mk={best_mk:.4f} ({best_mk-112.996:+.4f} vs bank) "
          f"[{time.time()-t0:.0f}s {ne} evals]", flush=True)
    return best_mk, best_enc


def main(topk=8, budget=40000):
    bank = json.load(open(BANK)); x0 = np.array(bank[0]["decisionVector"], float)
    bank_order = [round(v) for v in x0[2 * (n - 1):]]
    bank_mk = float(kt.fitness(list(x0))[0])
    # positive control: refine the bank order, must land ~<=112.996
    enc_bank = enc_from_schedule(x0[:n - 1], x0[n - 1:2 * (n - 1)])
    print(f"[control] bank official mk={bank_mk:.4f}; refining bank order as control...", flush=True)
    cmk, _ = refine(bank_order, enc_bank, 20000, "control-bank")
    if cmk > bank_mk + 0.5:
        print("[ABORT] control refine worse than bank — encoding bug.", flush=True); return
    print(f"[control] PASS (control {cmk:.4f} ~ bank {bank_mk:.4f}); refining LKH/DP orders.", flush=True)

    # load distinct candidate orders, best dp_mk first
    seen = {};
    for line in open(CAND):
        c = json.loads(line); key = tuple(c['perm'])
        if key not in seen or c['dp_mk'] < seen[key]['dp_mk']:
            seen[key] = c
    cands = sorted(seen.values(), key=lambda c: c['dp_mk'])[:topk]
    print(f"[start] {len(cands)} distinct candidate orders (dp_mk {cands[0]['dp_mk']:.3f}.."
          f"{cands[-1]['dp_mk']:.3f}); budget {budget}/order", flush=True)

    best_mk = bank_mk; best = None
    for i, c in enumerate(cands):
        enc0 = enc_from_schedule(c['times'], c['tofs'])
        mk, enc = refine(c['perm'], enc0, budget, f"cand{i}-dp{c['dp_mk']:.2f}")
        if mk < best_mk - 1e-6:
            best_mk = mk; best = (c['perm'], enc)
            print(f"  *** NEW OFFICIAL BEST mk={mk:.4f} < bank {bank_mk:.4f}", flush=True)

    if best is None:
        print(f"\n[done] no refined order beat bank {bank_mk:.4f}; small floor holds at this candidate set.",
              flush=True); return
    # guard-bank
    order, enc = best; times, tofs = decode(enc)
    dv = [float(x) for x in (list(times) + list(tofs) + [float(p) for p in order])]
    f = kt.fitness(dv); feasible = kt.is_feasible(f)
    print(f"\n[guard] best refined official mk={f[0]:.4f} feasible={feasible} viols={list(f[1:])}", flush=True)
    if feasible and f[0] < bank_mk - 1e-4:
        shutil.copy(BANK, BANK + ".bak.dpspace")
        json.dump([{"decisionVector": dv, "problem": "small"}], open(BANK, "w"))
        recheck = float(kt.fitness(json.load(open(BANK))[0]["decisionVector"])[0])
        print(f"[BANKED] small {bank_mk:.4f} -> {recheck:.4f} (backup .bak.dpspace). NOT submitted.", flush=True)
    else:
        json.dump({"dv": dv, "mk": float(f[0])}, open("/tmp/ch2_small_dpspace_winner.json", "w"))
        print("[no-bank] not strictly-better-feasible; dumped to /tmp.", flush=True)


if __name__ == "__main__":
    tk = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    bg = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
    main(tk, bg)
