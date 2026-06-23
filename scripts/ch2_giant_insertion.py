"""E-665: Ch2-large GIANT via time-aware CHEAPEST-INSERTION (pivot after greedy corner-paints, E-664).

Diagnosis (E-664): time-aware NEAREST-NEIGHBOR phases beautifully early (~0.3 d/leg, 150 cities in
~50d — the level TGMA reaches) but STRANDS: it myopically consumes the easy cheap-now cities and
paints itself into a corner where the hard remainder has no cheap window. Min-tof per leg ~0.15d
⇒ giant floor ~90d; TGMA 0.4 d/leg ⇒ ~240d vs our bank 913. So 913→~240 is a CONSTRUCTION problem.

CHEAPEST-INSERTION doesn't corner-paint: it grows the tour by inserting, at each step, the
(city, position) with the smallest makespan increase — globally aware, every city gets its slot.
Time-dependence: inserting u at position p shifts all DOWNSTREAM epochs, so cost is evaluated by a
fast TABLE retime of the candidate order (min-tof at the epoch bucket, with bounded waiting). The
WINNER each round is faithfully nothing — we keep it table-fast, then ONE faithful retime at the end
(find_earliest_transfer w/ DELAY waiting) decides vs 913. Heartbeats for sandbox survival.

Usage: python ch2_giant_insertion.py [wall_s] [n_seeds]
"""
import sys, json, time, random
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix
from esa_spoc_26.ch2_kttsp import KTTSP
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
TOF_WINDOW = 40.0; N_STEPS = 2400; HB = 100
DELAY = np.round(np.arange(0.0, 6.01, 0.5), 3)
_C = {}


def leg(kt, a, b, t):
    key = (a, b, round(t, 2))
    v = _C.get(key)
    if v is None:
        tof, dv = find_earliest_transfer(kt, a, b, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
        v = tof; _C[key] = v
    return v


def faithful_retime(kt, order, entry, tag=""):
    """Faithful makespan: per leg min-arrival over DELAY (bounded waiting). None if stranded."""
    t = entry; t0 = time.time()
    for k in range(len(order) - 1):
        best = None
        for d in DELAY:
            td = t + float(d)
            if td + 0.05 >= kt.max_time:
                break
            tof = leg(kt, order[k], order[k + 1], td)
            if tof is not None and (best is None or td + tof < best):
                best = td + tof
        if best is None:
            return None
        t = best
        if tag and (k + 1) % HB == 0:
            print(f"  [{tag}] leg {k+1}/{len(order)-1} ep={t:.0f} ({time.time()-t0:.0f}s)", flush=True)
    return t - entry


def tbl_tof(tab, epochs, a, b, t):
    """Table min-arrival for a->b departing >= t with bounded waiting; returns arrival or inf."""
    row = tab.get((a, b))
    if row is None:
        return np.inf
    bi0 = int(np.searchsorted(epochs, t)); ne = len(epochs)
    best = np.inf
    for bi in range(min(bi0, ne - 1), ne):
        dep = max(t, float(epochs[bi]))
        tof = row[bi]
        if np.isfinite(tof):
            arr = dep + tof
            if arr < best:
                best = arr
            if float(epochs[bi]) > best:
                break
    return best


def tbl_retime(tab, epochs, order, entry):
    """Fast table makespan of an order (bounded waiting). inf if any leg has no cheap window."""
    t = entry
    for k in range(len(order) - 1):
        arr = tbl_tof(tab, epochs, order[k], order[k + 1], t)
        if not np.isfinite(arr):
            return np.inf
        t = arr
    return t - entry


def insertion(tab, epochs, gnodes, start, entry, rng, log):
    """Time-aware cheapest insertion. Tour grows from [start]; each round insert the (city, pos)
    minimizing the table makespan of the resulting tour. To stay tractable we only evaluate
    insertion near the END (last W positions) — early epochs are locked once placed (the tour is
    time-ordered, so re-timing the whole prefix per candidate is wasteful). W=12 window."""
    W = 12
    remaining = [c for c in gnodes if c != start]
    rng.shuffle(remaining)
    tour = [start]; m = len(gnodes); t0 = time.time()
    while remaining:
        # prefix epochs: pe[i] = arrival epoch at tour[i] (one table walk, reused for all candidates)
        pe = [entry] * len(tour); tt = entry
        for i in range(1, len(tour)):
            tt = tbl_tof(tab, epochs, tour[i - 1], tour[i], tt); pe[i] = tt
        t_end = pe[-1]
        positions = range(max(1, len(tour) - W), len(tour) + 1)
        best = None  # (cost, city, pos)
        for u in remaining:
            for p in positions:
                a = tour[p - 1]
                arr_au = tbl_tof(tab, epochs, a, u, pe[p - 1])
                if not np.isfinite(arr_au):
                    continue
                if p < len(tour):
                    b = tour[p]
                    arr_ub = tbl_tof(tab, epochs, u, b, arr_au)
                    if not np.isfinite(arr_ub):
                        continue
                    cost = arr_ub - pe[p]              # makespan increase at b (vs current)
                else:
                    cost = arr_au - t_end              # append cost at end
                if best is None or cost < best[0]:
                    best = (cost, u, p)
        if best is None:                               # no feasible insertion anywhere in window
            # fallback: append the city with the earliest reachable arrival from the end
            cand = min(remaining, key=lambda u: tbl_tof(tab, epochs, tour[-1], u, t_end))
            if not np.isfinite(tbl_tof(tab, epochs, tour[-1], cand, t_end)):
                log(f"  insertion STUCK at {len(tour)}/{m} (no cheap window) — fail"); return None
            tour.append(cand); remaining.remove(cand)
        else:
            _, u, p = best
            tour.insert(p, u); remaining.remove(u)
        if len(tour) % 50 == 0:
            log(f"  insertion {len(tour)}/{m} t_end~{t_end:.0f} ({time.time()-t0:.0f}s)")
    return tour if len(set(tour)) == m else None


def main(seed=0, wall_s=20 * 3600, entry=0.0):
    kt = KTTSP(INST); n = kt.n
    adj = np.load('/tmp/ch2_e533_large_adj.npz')['cheap']
    nc, lab = connected_components(csr_matrix(adj), directed=False)
    gi = int(np.argmax(np.bincount(lab)))
    gnodes = [int(x) for x in np.where(lab == gi)[0]]; m = len(gnodes)
    d = np.load('/tmp/ch2_large_epoch_table.npz', allow_pickle=True)
    epochs = d['epochs']; tab = {(int(a), int(b)): r for (a, b), r in zip(d['keys'], d['vals'])}
    log = lambda s: print(f"[s{seed}] {s}", flush=True)
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]['decisionVector']
    bperm = [int(round(x)) for x in bank[2 * (n - 1):]]; gset = set(gnodes)
    bank_g = [c for c in bperm if c in gset]
    rng = random.Random(seed * 31 + 7)
    start = bank_g[0] if seed == 0 else gnodes[rng.randrange(m)]
    t0 = time.time()
    log(f"insertion build (start {start}, {m} cities; bank-giant=913, target ~240)")
    order = insertion(tab, epochs, gnodes, start, entry, rng, log)
    if order is None:
        log("insertion failed"); return
    tmk = tbl_retime(tab, epochs, order, entry)
    log(f"insertion DONE table-mk={tmk:.1f} [{time.time()-t0:.0f}s] — faithful retime next")
    fmk = faithful_retime(kt, order, entry, "faith")
    if fmk is None:
        log("insertion order STRANDS faithfully (wait>6d)"); return
    log(f"*** insertion FAITHFUL giant = {fmk:.1f}d (bank-giant 913) "
        f"{'BEATS BANK -> build full assembly' if fmk < 913 else 'no improvement'}")
    json.dump({'giant_order': order, 'table_mk': float(tmk), 'faithful_mk': float(fmk)},
              open(f'/tmp/ch2_insertion_giant_s{seed}.json', 'w'))


if __name__ == "__main__":
    import multiprocessing as mp
    wall = float(sys.argv[1]) if len(sys.argv) > 1 else 20 * 3600
    ns = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    ps = [mp.Process(target=main, args=(s, wall, 0.0)) for s in range(ns)]
    for p in ps: p.start()
    for p in ps: p.join()
