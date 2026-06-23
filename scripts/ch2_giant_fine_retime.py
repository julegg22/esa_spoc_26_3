"""E-710 M1' — DECISIVE: re-time an existing order with a FINE table-seeded tof search.

Chain of foundation findings: table is 100% faithful (M0b); cheap-tof bands are ~0.002d wide so coarse
(0.01-0.05d) scans miss ~89% of cheap edges (M0b); cheap windows are CONTINUOUS & wide (~12d) so a cheap
tof exists at essentially any departure (M0c). HYPOTHESIS: the memory's "beam overfit" (orders that look
0.3 d/leg on the table but 'retime to 1099d') was actually COARSE-TOF RETIMING BLINDNESS - the retimer
scanned 0.01-0.05d steps and missed the narrow cheap band, forcing long tofs. If so, re-timing with a FINE
table-seeded tof search COLLAPSES the makespan.

Test: re-time the BANK's complete 601-order (E-709 coarse-tof walk got 931d) with fine tof. Also the table
min-arrival greedy order. If makespan drops toward/below 424 -> coarse-tof was the flaw the whole time.
Usage: python ch2_giant_fine_retime.py"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
kt = KTTSP(INST); n = kt.n
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}


def fine_cheap_tof(i, j, t, dv_cap):
    """Smallest cheap (<=dv_cap) tof departing at exact time t, table-seeded fine search. None if not cheap."""
    row = PIDX.get((i, j))
    hints = []
    if row is not None:
        e = np.searchsorted(EPOCHS, t)
        for ee in (e, e - 1, e + 1, e - 2, e + 2):                 # nearest grid epochs (1d spacing)
            if 0 <= ee < len(EPOCHS) and FIN[row, ee]:
                hints.append(float(VALS[row, ee]))
    cand = set()
    for h in hints:                                                # fine band around each hint
        for tof in np.arange(max(kt.min_tof, h - 0.03), h + 0.03, 0.0005):
            cand.add(round(tof, 5))
    if not hints:                                                  # no table hint: coarse fallback scan
        for tof in np.arange(kt.min_tof, 1.0, 0.01):
            cand.add(round(tof, 5))
    best = None
    for tof in sorted(cand):
        if kt.compute_transfer(i, j, t, float(tof)) <= dv_cap:
            best = float(tof); break
    return best


def retime(order, label):
    t = 0.0; mk = 0.0; exc = 0; strands = 0; tofs = []; t0 = time.time()
    for k in range(len(order) - 1):
        i, j = order[k], order[k + 1]
        tof = fine_cheap_tof(i, j, t, kt.dv_thr)
        if tof is None and exc < kt.n_exc:
            tof = fine_cheap_tof(i, j, t, kt.dv_exc)
            if tof is not None:
                exc += 1
        if tof is None:
            strands += 1
            break
        tofs.append(tof); t += tof; mk = t
        if (k + 1) % 150 == 0:
            print(f"  [{label}] leg {k+1}/{len(order)-1}: t={t:.1f}d exc={exc} mean_tof={np.mean(tofs):.3f} [{time.time()-t0:.0f}s]", flush=True)
    done = len([x for x in range(len(order) - 1)]) if strands == 0 else k
    print(f"[E-710 M1'] {label}: reached {k+1 if strands==0 else k}/{len(order)-1} legs, makespan={mk:.1f}d, "
          f"exc={exc}, strands={strands}, mean cheap tof={np.mean(tofs):.4f}d [{time.time()-t0:.0f}s]", flush=True)
    return mk, (strands == 0), order[:(k + 1 if strands == 0 else k)]


def main():
    x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
    order = [round(v) for v in x[2 * (n - 1):]]
    bank_mk = x[:n - 1][-1] + x[n - 1:2 * (n - 1)][-1]
    print(f"[E-710 M1'] FINE table-seeded retime. bank coarse-walk=931d, bank actual={bank_mk:.1f}d, rank-1=424.62", flush=True)
    mk, ok, _ = retime(order, "bank-order")
    if ok and mk < 500:
        print(f"[E-710 M1'] *** BREAKTHROUGH: bank order retimes to {mk:.1f}d with FINE tof (<500) -> coarse-tof "
              f"retiming was THE FLAW; we are at/near rank-1 territory. Build fine-tof guard-bank + verify with udp.", flush=True)
    elif ok and mk < bank_mk - 100:
        print(f"[E-710 M1'] fine retime drops {bank_mk:.0f}->{mk:.0f}d (-{bank_mk-mk:.0f}) but not <500; partial lever.", flush=True)
    else:
        print(f"[E-710 M1'] fine retime did NOT collapse the bank order ({mk:.0f}d) -> the bank ORDER itself is "
              f"long-tof-bound; need a different (fine-tof-constructed) order, not just retiming.", flush=True)


if __name__ == "__main__":
    main()
