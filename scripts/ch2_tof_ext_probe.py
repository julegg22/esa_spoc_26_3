"""E-705 — Ch2-small lever (b): does extending tof past 8.0d ADD earlier-arriving cheap edges?

Cheap decisive probe BEFORE the multi-hour extended-table rebuild. The ultrafine table caps tof at 8.0d.
Hypothesis: a better order uses a cheap (dv<=100) tof>8d transfer the table is missing. But a long-tof
edge only helps makespan if departing-NOW on it arrives EARLIER than waiting for the table's next short
cheap window. For each edge pair at a coarse epoch grid, scan tof in (8,25]; if a cheap edge there
arrives earlier than the existing table's best cheap option from that epoch, tof>8 helps that pair.

Usage: python ch2_tof_ext_probe.py [workers=4]"""
import sys, time
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TABLE = f"{ROOT}/cache/ch2_small_tcoupled_ultrafine.npz"
d = np.load(TABLE); CHEAP = d["cheap"]; TS = d["t_starts"]; Q = float(TS[1] - TS[0]); T = len(TS)
EP = np.arange(0, T, 40)              # coarse epoch grid (~2d)
TOF_EXT = np.arange(8.25, 25.01, 0.5)  # extended tof range
_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _best_existing_arrival(i, j, q):
    """min over epoch'>=q of epoch'*Q + cheap[i,j,epoch'] (earliest cheap arrival using the 8d-cap table)."""
    ci = CHEAP[i, j, q:]; fin = np.isfinite(ci)
    if not fin.any():
        return np.inf
    qs = np.arange(q, T)[fin]
    return float((qs * Q + ci[fin]).min())


def _scan(args):
    i, j = args; kt = _KT[0]; helps = 0; best_gain = 0.0
    for q in EP:
        ts = q * Q
        if ts + 25 > kt.max_time:
            break
        base = _best_existing_arrival(i, j, int(q))
        for tof in TOF_EXT:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= 100.0:
                arr = ts + tof
                if arr < base - 0.05:        # extended-tof cheap edge arrives EARLIER than table's best
                    helps += 1; best_gain = max(best_gain, base - arr)
                break                        # earliest cheap tof in extended range is enough
    return i, j, helps, best_gain


def main(workers=4):
    kt = KTTSP(INST); n = kt.n
    edge_pairs = [tuple(p) for p in np.load(f"{ROOT}/cache/ch2_small_edgepairs.npy")]
    print(f"[E-705] probing {len(edge_pairs)} edge pairs x {len(EP)} epochs x {len(TOF_EXT)} ext-tofs", flush=True)
    t0 = time.time(); npairs_help = 0; tot_help = 0; max_gain = 0.0; done = 0
    with mp.Pool(workers, initializer=_init) as p:
        for i, j, helps, gain in p.imap_unordered(_scan, edge_pairs, chunksize=4):
            if helps > 0:
                npairs_help += 1; tot_help += helps; max_gain = max(max_gain, gain)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(edge_pairs)} | pairs-helped {npairs_help} max_gain {max_gain:.2f}d [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-705] VERDICT: {npairs_help}/{len(edge_pairs)} pairs gain an EARLIER-arriving cheap edge via tof>8d "
          f"({tot_help} epoch-instances, max earlier-by {max_gain:.2f}d)", flush=True)
    if npairs_help >= 50:
        print(f"[E-705] -> tof>8 ADDS meaningful earlier-arrival cheap reachability -> build the extended table + walk-SA.", flush=True)
    else:
        print(f"[E-705] -> tof>8 adds little/no earlier-arrival cheap reachability -> hypothesis WEAK; "
              f"Ch2-small lever (b) likely dead (consistent with competitor 2.1 d/leg = short legs, not long).", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(w)
