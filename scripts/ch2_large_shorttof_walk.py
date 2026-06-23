"""E-709 — Ch2-large audit: re-time the BANK ORDER with a DENSE short-tof scan.

The cheap-edge adjacency (e533) probed only 8 (t_start,tof) points, shortest tof 0.5d -> it is BLIND to
short cheap edges (tof<0.5d), yet min_tof=0.0007d and rank-1's 0.404 d/leg implies abundant ~0.1-0.4d
cheap legs. Decisive test: take the bank's node ORDER, and for each leg find the SMALLEST cheap (dv<=100)
tof at the current epoch (fine scan from min_tof); walk chronologically (<=5 exceptions). If the makespan
collapses from 932 toward ~400, the gap is TIMING/short-edges the 8-probe graph never saw -> the
"time-ordering wall" is an adjacency artifact, and a dense short-tof rebuild reaches rank-1 territory.
Usage: python ch2_large_shorttof_walk.py [tof_max=3.0] [step=0.01]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/large.json"
kt = KTTSP(INST); n = kt.n


def smallest_cheap_tof(i, j, t, tof_grid, dv_cap):
    """smallest tof in tof_grid with compute_transfer(i,j,t,tof) <= dv_cap, else None."""
    for tof in tof_grid:
        try:
            if kt.compute_transfer(i, j, float(t), float(tof)) <= dv_cap:
                return float(tof)
        except Exception:
            continue
    return None


def main(tof_max=3.0, step=0.01):
    x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    order = [round(v) for v in x[2 * (n - 1):]]
    bank_mk = x[:n - 1][-1] + x[n - 1:2 * (n - 1)][-1]
    grid = np.concatenate([np.arange(kt.min_tof, 0.5, step), np.arange(0.5, tof_max, 5 * step)])
    print(f"[E-709] bank makespan {bank_mk:.2f}d (rank-1 424.62). Re-timing bank ORDER, dense short-tof "
          f"(min_tof {kt.min_tof:.4f}d, {len(grid)} tofs), n_exc={kt.n_exc}", flush=True)
    t = 0.0; mk = 0.0; exc_used = 0; strands = 0; cheap_tofs = []; t0 = time.time()
    for k in range(n - 1):
        i, j = order[k], order[k + 1]
        tof = smallest_cheap_tof(i, j, t, grid, kt.dv_thr)              # cheap first
        is_exc = False
        if tof is None and exc_used < kt.n_exc:
            tof = smallest_cheap_tof(i, j, t, grid, kt.dv_exc); is_exc = (tof is not None)
        if tof is None:
            # no cheap and no exc budget: wait one step grid OR record strand (use bank's tof as fallback)
            tof = float(x[n - 1 + k]); strands += 1
        else:
            cheap_tofs.append(tof)
            if is_exc:
                exc_used += 1
        t = t + tof; mk = t
        if (k + 1) % 150 == 0:
            print(f"  leg {k+1}/{n-1}: t={t:.1f}d exc={exc_used} strands={strands} mean_tof={np.mean(cheap_tofs):.3f} [{time.time()-t0:.0f}s]", flush=True)
    print(f"\n[E-709] dense-short-tof walk of BANK ORDER: makespan={mk:.2f}d (bank {bank_mk:.2f}, rank-1 424.62)", flush=True)
    print(f"  exc_used={exc_used}/{kt.n_exc}  strands(no cheap/exc found)={strands}  mean cheap tof={np.mean(cheap_tofs):.3f}d (bank mean 0.860)", flush=True)
    if mk < bank_mk - 50:
        print(f"[E-709] -> makespan COLLAPSES -> the gap is TIMING/short-edges the 8-probe adjacency never saw. "
              f"Dense short-tof rebuild + global search reaches rank-1 territory. Adjacency/'wall' was the FLAW.", flush=True)
    else:
        print(f"[E-709] -> no collapse -> short-tof timing alone insufficient for the bank order; "
              f"gap is in the ORDER (genuine global re-interleaving). Adjacency may still be under-sampled for OTHER orders.", flush=True)


if __name__ == "__main__":
    tm = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    st = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    main(tm, st)
