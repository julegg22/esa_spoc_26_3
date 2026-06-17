"""L2 — Ch2-LARGE short-ToF + wide-epoch edge probe (assumption A1).

Large precompute samples ToF [0.025,8] d and epoch [0,200] d, but the problem allows
ToF>=0.0007 d and the bank timeline runs to ~932 d. This scans, for the bank-order
legs (sampled), the UNSAMPLED short-ToF regime [0.0007,0.025) AND wide epochs >200 d,
counting faster cheap (dv<=100) edges the table never computed. n=1051 so we probe the
~1050 bank-order legs (not all 1051^2 pairs) — these are the legs that actually matter.

If meaningful faster cheap edges exist there -> A1 falsified, the order/edge search ran
on a truncated, slow candidate set (the Ch1 sparse-matrix / small-S2 analog at scale).
Instrumented per M-general-instrument-experiments-before-launch.
Usage: python ch2_l2_shorttof_probe.py [nworkers=4]
"""
import sys, json, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        f"Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
SHORT_TOFS = np.linspace(0.0007, 0.0245, 10)   # UNSAMPLED short regime
_KT = {}

def _init():
    from esa_spoc_26.ch2_kttsp import KTTSP
    _KT[0] = KTTSP(INST)

def probe_leg(args):
    """For one bank leg (i,j) at its banked epoch t_bank with banked tof t_walked:
    (a) min dv over SHORT tofs at t_bank; (b) min cheap tof over a WIDE epoch sweep."""
    i, j, t_bank, t_walked = args; kt = _KT[0]
    short_best = 1e9
    for tof in SHORT_TOFS:
        try:
            dv = kt.compute_transfer(i, j, float(t_bank), float(tof))
        except Exception:
            continue
        short_best = min(short_best, dv)
    # wide-epoch: cheapest SHORT cheap tof anywhere in [0, 932]
    wide_best_tof = 99.0
    for t in np.arange(0.0, 932.0, 5.0):
        for tof in SHORT_TOFS:
            if tof >= wide_best_tof:
                break
            try:
                if kt.compute_transfer(i, j, float(t), float(tof)) <= kt.dv_thr + 1e-6:
                    wide_best_tof = tof; break
            except Exception:
                continue
    return i, j, short_best, wide_best_tof, t_walked

def main(nw=4):
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST); n = kt.n
    x = np.array(json.load(open(BANK))[0]["decisionVector"])
    times = x[:n-1]; tofs = x[n-1:2*n-2]; order = [round(v) for v in x[2*n-2:]]
    _KT[0] = kt
    cd = kt.compute_transfer(order[0], order[1], float(times[0]), 0.01)
    print(f"L2 control: compute_transfer(bank leg0, tof=0.01) -> dv={cd:.0f} (evaluator live)", flush=True)
    # sample ~200 bank legs evenly
    idx = np.linspace(0, n-2, 200).round().astype(int)
    legs = [(order[k], order[k+1], float(times[k]), float(tofs[k])) for k in idx]
    print(f"L2: probing {len(legs)} sampled bank legs; short-ToF [0.0007,0.025) + wide-epoch sweep; "
          f"~{len(legs)*(186*10+10)*5e-4/nw/60:.0f}min", flush=True)
    cheap_short = 0; faster = 0; ndone = 0; t0 = time.time(); examples = []
    with mp.Pool(nw, initializer=_init) as p:
        for i, j, sdv, wtof, twalk in p.imap_unordered(probe_leg, legs, chunksize=2):
            ndone += 1
            if sdv <= kt.dv_thr + 1e-6:
                cheap_short += 1
            if wtof < twalk - 0.05:   # a cheap edge with SHORTER tof than the walked leg exists
                faster += 1; examples.append((i, j, wtof, twalk))
            if ndone % 40 == 0:
                print(f"  [{ndone}/{len(legs)}] cheap-at-short-tof={cheap_short} faster-than-walked={faster} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"\n=== L2 DONE ({len(legs)} sampled bank legs) ===", flush=True)
    print(f"  cheap edges at SHORT tof (<0.025, at banked epoch): {cheap_short}/{len(legs)}", flush=True)
    print(f"  legs with a SHORTER cheap tof available (wide-epoch): {faster}/{len(legs)} "
          f"(median walked tof was {np.median(tofs):.3f}d)", flush=True)
    examples.sort(key=lambda e: e[2]-e[3])
    for i, j, wt, walk in examples[:12]:
        print(f"    {i}->{j}: short cheap tof={wt:.4f}d vs walked {walk:.3f}d", flush=True)
    if cheap_short > 0 or faster > 0:
        print(f"  -> A1 FALSIFIED: faster cheap edges exist below the table's ToF floor / outside its "
              f"epoch window -> large order search ran on a truncated SLOW candidate set.", flush=True)
    else:
        print(f"  -> no faster cheap edges found; A1 holds (table floor/window benign for large).", flush=True)

if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(nw)
