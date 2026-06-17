"""S1 — free-epoch GLOBAL retiming of the Ch2-small BANK ORDER (assumption A2/A5/A6).

Falsifies the order-centric architecture: fix the bank permutation, globally optimize
its schedule (epochs+ToFs as FREE continuous vars) on the OFFICIAL kt.fitness with
CMA-ES (tolerates the discontinuous Lambert landscape where SLSQP failed). If makespan
drops below the banked 189.10 for the SAME order, the gap is SCHEDULE optimization, not
order search — the whole order-search tree attacked the wrong layer.

Encoding (monotone by construction): vars = [t0, tof_0..47, wait_0..46] (96), waits>=0,
tofs>=min_tof; times[i+1]=times[i]+tof[i]+wait[i]. Objective = makespan + penalty(legs
with dv>600, exceptions>5). Instrumented per M-general-instrument-experiments-before-launch.
Usage: python ch2_s1_freeepoch_retime.py [budget_evals=200000]
"""
import sys, json, time
import numpy as np
import cma
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/medium.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/medium.json"
kt = KTTSP(INST); n = kt.n
x0 = np.array(json.load(open(BANK))[0]["decisionVector"], dtype=float)
order = [round(v) for v in x0[2*(n-1):]]
bt = x0[:n-1]; bf = x0[n-1:2*(n-1)]                       # bank times, tofs
# bank -> encoding (t0, tofs, waits)
waits0 = np.array([bt[i+1]-(bt[i]+bf[i]) for i in range(n-2)])
enc0 = np.concatenate([[bt[0]], bf, np.maximum(waits0, 0)])  # 1+48+47 = 96

def decode(enc):
    t0 = enc[0]; tofs = np.maximum(enc[1:n], kt.min_tof); waits = np.maximum(enc[n:], 0.0)
    times = np.empty(n-1); times[0] = max(t0, 0.0)
    for i in range(n-2):
        times[i+1] = times[i] + tofs[i] + waits[i]
    return times, tofs

def evalx(enc):
    times, tofs = decode(enc)
    f = kt.fitness(list(times) + list(tofs) + [float(o) for o in order])
    mk = f[0]
    pen = 1000.0*(abs(f[2]) + abs(f[3]) + max(0.0, f[4]))   # dv>600 legs, monotone(should be 0), exc>5
    if times[-1]+tofs[-1] > kt.max_time: pen += 1000.0*(times[-1]+tofs[-1]-kt.max_time)
    return mk + pen, mk, kt.is_feasible(f)

def main(budget=200000):
    # POSITIVE CONTROL: reconstructed bank must reproduce 189.10 feasible
    obj0, mk0, feas0 = evalx(enc0)
    print(f"S1 startup control: reconstructed bank makespan={mk0:.4f} feasible={feas0} "
          f"(expect 189.10) obj={obj0:.4f}", flush=True)
    if not feas0 or abs(mk0-189.10) > 0.5:
        print("  ABORT: control does not reproduce bank — encoding/evaluator bug.", flush=True); return
    print(f"S1: CMA-ES over 96 schedule vars of FIXED bank order; budget={budget} evals", flush=True)
    es = cma.CMAEvolutionStrategy(enc0, 0.3, {
        'maxfevals': budget, 'popsize': 24, 'bounds': [0.0, None], 'verbose': -9, 'seed': 1})
    best_mk = mk0; best_enc = enc0.copy(); n_eval = 0; t0 = time.time(); last = t0
    while not es.stop():
        sols = es.ask()
        vals = []
        for s in sols:
            o, mk, feas = evalx(s); vals.append(o); n_eval += 1
            if feas and mk < best_mk:
                best_mk = mk; best_enc = s.copy()
                print(f"  [{n_eval}] NEW BEST makespan={mk:.4f} (bank 189.10, {mk-189.10:+.4f}) "
                      f"[{time.time()-t0:.0f}s]", flush=True)
        es.tell(sols, vals)
        if time.time()-last > 30:
            print(f"  [{n_eval}] best={best_mk:.4f} sigma={es.sigma:.3f} [{time.time()-t0:.0f}s]", flush=True)
            last = time.time()
    print(f"\n=== S1 DONE: best feasible makespan = {best_mk:.4f} vs bank 189.10 ({best_mk-189.10:+.4f}) "
          f"over {n_eval} evals ===", flush=True)
    if best_mk < 189.10 - 1e-3:
        times, tofs = decode(best_enc)
        dv = list(times)+list(tofs)+[float(o) for o in order]
        fit = kt.fitness(dv)
        print(f"  -> SCHEDULE-LAYER FLAW CONFIRMED: better schedule for SAME order, official mk={fit[0]:.4f} "
              f"feas={kt.is_feasible(fit)}; saved /tmp/ch2_s1_winner.json", flush=True)
        json.dump({"makespan": float(fit[0]), "decisionVector": dv}, open("/tmp/ch2_s1_winner.json","w"))
        print(f"  -> implication: order-centric search attacked the wrong layer; build joint free-epoch search.", flush=True)
    else:
        print(f"  -> bank schedule is ~optimal for its order; the gap is in ORDER/EDGE space, not schedule.", flush=True)

if __name__ == "__main__":
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    main(budget)
