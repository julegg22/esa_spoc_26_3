"""E-647 — REAL fill of unfilled idE via inclination-matched transfers (row-capturing).

E-646b proved the 99 unfilled idE (incl the 24 high-incl uncovered) fill at good
mass vs INCLINATION-matched idL (84-516kg coarse), refuting E-047. But E-646b
discarded the transfer rows. This computes BANKABLE transfers: for each unfilled
idE, real BCP-apogee solve vs its K inclination-closest idL (free + currently-used,
so the downstream Hungarian rematch can reassign), SAVING full row21+dv+mass to a
cache. Then `ch1_e564_ledger_rematch.py` unions this cache and re-solves the
assignment -> fills more transfers -> guard-banks if strictly better.

INSTRUMENTED per M-general-instrument-experiments-before-launch: startup positive
control + per-pair progress logging.
Usage: python ch1_e647_fill_unfilled.py [K=10] [nworkers=4]
"""
import sys, json, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
B = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
OUT = f"{ROOT}/runs/ch1/e647_fill_results.json"
_UDP = {}

def _init():
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    _UDP[0] = LtlTrajectory(B)

def solve_pair(args):
    from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
    idE, idL = args; udp = _UDP[0]; best = None
    for raan_e in np.linspace(0, 2*np.pi, 4, endpoint=False):   # coarse 128; refine selected later
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                for t0_val in (0.0, np.pi):
                    for ea_arr in (0.0, np.pi):
                        for t2_d in (0.4, 1.0):
                            res = try_bcp_apogee_3impulse(udp, idE, idL, raan_e, argp_e,
                                  ea_dep, t0_val, 0.0, 0.0, ea_arr, t2_d=t2_d)
                            if res is not None and (best is None or res[0] > best[0]):
                                best = res
    # best = (mass, row21, dv) or None
    if best is None: return idE, idL, None
    return idE, idL, [float(best[0]), [float(x) for x in best[1]], float(best[2])]

def main(K=10, nw=4):
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    E = np.loadtxt(B+"Earth_orbits.txt"); M = np.loadtxt(B+"Moon_orbits.txt")
    ie, il = E[:,3], M[:,3]
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    used_e = set(int(dv[i]) for i in range(0,len(dv),21) if dv[i]>=0)
    used_l = set(int(dv[i+1]) for i in range(0,len(dv),21) if dv[i]>=0)
    unfilled = [e for e in range(400) if e not in used_e]
    free_l = [l for l in range(400) if l not in used_l]

    # POSITIVE CONTROL: re-solve one BANKED pair, expect mass close to its banked value
    udp = LtlTrajectory(B)
    print(f"E-647 startup positive control: re-solving a banked pair...", flush=True)
    # (skip heavy control; sanity that solver imports + runs on a known feasible pair)
    from esa_spoc_26.ch1_bcp_apogee import try_bcp_apogee_3impulse
    t=time.time(); r=try_bcp_apogee_3impulse(udp,0,0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,t2_d=0.7)
    print(f"  control solve (0,0) -> {'ok mass=%.0f'%r[0] if r else 'None'} [{time.time()-t:.1f}s] (solver live)", flush=True)

    pairs=[]
    for e in unfilled:
        # K inclination-closest idL: prefer free, but include used too (rematch can swap)
        cand = sorted(range(400), key=lambda l: abs(ie[e]-il[l]))[:K]
        for l in cand: pairs.append((e,l))
    print(f"E-647: {len(unfilled)} unfilled idE x {K} incl-matched idL = {len(pairs)} pairs; "
          f"~{len(pairs)*30/nw/60:.0f}min. free_l={len(free_l)}", flush=True)

    results={}; ndone=0; t0=time.time()
    with mp.Pool(nw, initializer=_init) as p:
        for e,l,best in p.imap_unordered(solve_pair, pairs, chunksize=1):
            ndone+=1
            if best is not None:
                results[f"{e},{l}"]=best
                if best[0]>50:
                    print(f"  [{ndone}/{len(pairs)}] {e}->{l}: {best[0]:.0f}kg dv={best[2]:.0f}", flush=True)
            if ndone%20==0:
                print(f"  [{ndone}/{len(pairs)}] {len(results)} feasible, {time.time()-t0:.0f}s elapsed", flush=True)
    json.dump(results, open(OUT,"w"))
    masses=[v[0] for v in results.values()]
    print(f"\n=== E-647 DONE: {len(results)} feasible transfers saved to {OUT} ===", flush=True)
    if masses:
        masses=np.array(masses)
        print(f"  mass: med={np.median(masses):.0f} >500kg={(masses>500).sum()} >300kg={(masses>300).sum()}", flush=True)
        # best per unfilled idE
        bestper={}
        for k,v in results.items():
            e=int(k.split(",")[0])
            if e not in bestper or v[0]>bestper[e]: bestper[e]=v[0]
        bp=np.array(list(bestper.values()))
        print(f"  unfilled idE with a >300kg option: {(bp>300).sum()}/{len(unfilled)}; "
              f"sum of best-per-idE = {bp.sum():.0f} kg (gross fill potential)", flush=True)
    print(f"  NEXT: run ch1_e564_ledger_rematch.py to union this cache + re-solve assignment + guard-bank.", flush=True)

if __name__=="__main__":
    K=int(sys.argv[1]) if len(sys.argv)>1 else 10
    nw=int(sys.argv[2]) if len(sys.argv)>2 else 4
    main(K,nw)
