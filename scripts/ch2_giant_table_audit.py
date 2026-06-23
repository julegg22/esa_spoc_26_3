"""E-710 M0b — audit the cached 1d table's PRECISION before building search on it.

M0/M1 revealed the table claims cheap where the faithful evaluator finds nothing (false positives), and its
stored tof is off enough that a narrow verify misses real cheap tofs. Decisive characterization:
for N table-cheap cells (epoch e, stored tof v), measure
  (1) FALSE-POSITIVE rate: is compute_transfer(i,j,EPOCHS[e], v) actually <= dv_thr?
  (2) if a full faithful scan AT THAT EPOCH finds cheap, how far is the true min-tof from the stored v?
This tells us whether the table is usable as a candidate proposer (tolerate FPs via a cheap verify) and
how wide the tof-refinement must be. Foundation-first: know the evaluator before trusting it.
Usage: python ch2_giant_table_audit.py [n=200]"""
import sys, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]
FIN = np.isfinite(VALS)


def scan_min_tof(i, j, t, hi=1.0):
    for tof in np.arange(kt.min_tof, hi, 0.01):
        if kt.compute_transfer(i, j, float(t), float(tof)) <= kt.dv_thr:
            return float(tof)
    return None


def main(n=200):
    rng = np.random.default_rng(0)
    cells = np.argwhere(FIN)                                        # (row, epoch) table-cheap cells
    idx = rng.choice(len(cells), size=n, replace=False)
    print(f"[E-710 M0b] auditing {n} table-cheap cells (precision of cache/ch2_giant_dense1d.npz)", flush=True)
    exact_ok = 0; scan_cheap = 0; tof_gaps = []; fp = 0; t0 = time.time()
    for k, ii in enumerate(idx):
        row, e = int(cells[ii][0]), int(cells[ii][1])
        i, j = int(KEYS[row][0]), int(KEYS[row][1])
        dep = float(EPOCHS[e]); vtof = float(VALS[row, e])
        # (1) does the stored (epoch,tof) verify faithfully?
        exact = kt.compute_transfer(i, j, dep, vtof) <= kt.dv_thr
        exact_ok += exact
        # (2) does a full scan at this epoch find cheap, and how far is the true tof?
        true_tof = scan_min_tof(i, j, dep)
        if true_tof is not None:
            scan_cheap += 1
            tof_gaps.append(abs(true_tof - vtof))
        else:
            fp += 1                                                # table-cheap but NOTHING cheap at this epoch
        if (k + 1) % 50 == 0:
            print(f"  {k+1}/{n}: exact_ok={exact_ok} scan_cheap={scan_cheap} hard_FP={fp} [{time.time()-t0:.0f}s]", flush=True)
    gaps = np.array(tof_gaps)
    print(f"\n[E-710 M0b] RESULTS on {n} table-cheap cells:", flush=True)
    print(f"  stored (epoch,tof) verifies faithfully: {exact_ok}/{n} ({100*exact_ok/n:.0f}%)", flush=True)
    print(f"  full scan at epoch finds cheap:         {scan_cheap}/{n} ({100*scan_cheap/n:.0f}%)", flush=True)
    print(f"  HARD false positives (nothing cheap at epoch): {fp}/{n} ({100*fp/n:.0f}%)", flush=True)
    if len(gaps):
        print(f"  tof gap |true - stored| (when scan-cheap): med {np.median(gaps):.3f}d  p90 {np.percentile(gaps,90):.3f}d  max {gaps.max():.3f}d", flush=True)
    print(f"[E-710 M0b] VERDICT: FP={100*fp/n:.0f}% sets candidate-pruning waste; tof-gap sets refine width. "
          f"If FP<15% and p90 gap<0.1d -> table is a usable proposer (cheap verify recovers). "
          f"If FP high -> table corrupt, rebuild candidate oracle.", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
