"""E-552 — Ch2 medium: EXPAND the fine pair table (E-551 verdict).

E-551 instrumented E-549's 96% DP rejects: missing_pair dominates every
operator (M5 199/200, M2 156/200, M1 172/200, random 200/200). The
curated 4686-pair table is the binding constraint, not the search.

Expansion set:
  1. ALL intra-component directed pairs (15660 total, ~10979 to add)
     — M1/M2 mutations only permute within components, so full intra
     coverage makes them table-complete.
  2. Inter-comp missing pairs observed by E-551 (top_missing list)
     — M5 bridge swaps relocate bridge endpoints.

Scans ONLY pairs absent from the existing table, merges into the dense
(n, n, T) arrays, saves v2. Checkpoints completed rows every 1500 pairs.

Output: /tmp/ch2_medium_fine_pair_set_v2.npz (same format as E-542)
"""
from __future__ import annotations
import sys, json, time
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/medium.kttsp")
COARSE = '/tmp/ch2_medium_tcoupled.npz'
FINE_V1 = '/tmp/ch2_medium_fine_pair_set.npz'
E551 = '/tmp/ch2_e551_reject_instrument.json'
OUT = '/tmp/ch2_medium_fine_pair_set_v2.npz'
CKPT = '/tmp/ch2_e552_ckpt.npz'

T_QUANTUM = 0.1
T_STARTS = np.arange(0.0, 500.0, T_QUANTUM)  # 5000 buckets (must match v1 for dense merge)
# All new pairs are coarse-exc-only (v1 already holds every coarse-cheap pair),
# so they never early-break and pay the full T x TOFS scan (~38s/pair @100 tofs).
# Stored table holds actual tof values per bucket, so a coarser scan grid here is
# merge-compatible; 40 tofs (0.3d res) is ample for these rarely-used exc legs and
# is ~2.5x faster. Bank/v1 cheap pairs retain their 100-tof resolution.
TOFS = np.linspace(0.025, 12.0, 40)
# Departure-bucket cap: every tour leg departs strictly before the makespan
# (bank=229d, target<199d), so buckets above 250d are never used by the DP.
# Scanning only 0-250d leaves higher buckets as INF (merge-safe) and ~halves
# the cost. 250d keeps a >20d margin above the current bank makespan.
SCAN_MAX_T = 250.0
DV_CAP = 100.0
DV_EXC = 600.0

_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan(args):
    pair_idx, i, j = args
    kt = _KT[0]
    n_t = len(T_STARTS)
    cheap = np.full(n_t, np.inf, dtype=np.float32)
    exc = np.full(n_t, np.inf, dtype=np.float32)
    for ki, ts in enumerate(T_STARTS):
        if ts > SCAN_MAX_T or ts + TOFS[-1] > kt.max_time:
            break
        for tof in TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= DV_CAP:
                cheap[ki] = tof
                exc[ki] = tof
                break
            elif dv <= DV_EXC and tof < exc[ki]:
                exc[ki] = tof
    return pair_idx, cheap, exc


def get_components(n):
    d = np.load(COARSE)
    cheap_min = np.nanmin(d['cheap'], axis=2)
    np.fill_diagonal(cheap_min, np.inf)
    adj_sym = np.isfinite(cheap_min) | np.isfinite(cheap_min.T)
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    _, lbl = csg.connected_components(sp.csr_matrix(adj_sym), directed=False)
    return {i: int(lbl[i]) for i in range(n)}


def main(workers=4):
    kt = KTTSP(INST)
    n = kt.n
    print(f"E-552 expanded fine precompute. n={n}", flush=True)

    d1 = np.load(FINE_V1)
    cheap_dense = d1['cheap'].copy()
    exc_dense = d1['exc'].copy()
    have = {(int(i), int(j)) for i, j in d1['pair_set']}
    print(f"Existing table: {len(have)} pairs", flush=True)

    node_comp = get_components(n)
    # Coarse feasibility prefilter: a pair with NO finite coarse cheap/exc
    # entry is (almost surely) infeasible at fine resolution too. Scanning
    # it does a full no-break 5000x100 sweep AND only adds all-INF cells the
    # DP would reject anyway. So restrict the new intra set to coarse-feasible
    # pairs (cheap OR exc finite at some coarse bucket).
    cd = np.load(COARSE)
    coarse_cheap_min = np.nanmin(cd['cheap'], axis=2)
    coarse_exc_min = np.nanmin(cd['exc'], axis=2)
    coarse_feasible = np.isfinite(coarse_cheap_min) | np.isfinite(coarse_exc_min)
    new_pairs = set()
    n_intra_all = 0
    for i in range(n):
        for j in range(n):
            if i != j and node_comp[i] == node_comp[j] and (i, j) not in have:
                n_intra_all += 1
                if coarse_feasible[i, j]:
                    new_pairs.add((i, j))
    n_intra = len(new_pairs)
    e551 = json.loads(Path(E551).read_text())
    for (i, j), _cnt in e551['top_missing']:
        if (int(i), int(j)) not in have:
            new_pairs.add((int(i), int(j)))
    print(f"New pairs: {n_intra} intra-comp (of {n_intra_all} candidate, "
          f"coarse-feasible prefiltered) + "
          f"{len(new_pairs)-n_intra} inter-comp (from E-551) "
          f"= {len(new_pairs)}", flush=True)

    pair_list = sorted(new_pairs)
    n_pairs = len(pair_list)
    n_t = len(T_STARTS)
    total_cells = n_pairs * n_t * len(TOFS)
    print(f"Total cells: {total_cells:,}  est wall on {workers} cores: "
          f"~{total_cells * 8e-6 / workers / 3600:.1f}h", flush=True)

    cheap_table = np.full((n_pairs, n_t), np.inf, dtype=np.float32)
    exc_table = np.full((n_pairs, n_t), np.inf, dtype=np.float32)
    done_mask = np.zeros(n_pairs, dtype=bool)

    # Resume from checkpoint if present
    if Path(CKPT).exists():
        ck = np.load(CKPT)
        ck_pairs = [tuple(p) for p in ck['pair_list']]
        if ck_pairs == pair_list:
            cheap_table = ck['cheap_table']
            exc_table = ck['exc_table']
            done_mask = ck['done_mask']
            print(f"Resumed checkpoint: {int(done_mask.sum())}/{n_pairs} done",
                  flush=True)

    args = [(k, p[0], p[1]) for k, p in enumerate(pair_list)
            if not done_mask[k]]
    t0 = time.time()
    start_done = int(done_mask.sum())
    done = start_done
    last_ckpt = done
    with mp.Pool(workers, initializer=_init) as pool:
        for k, c, e in pool.imap_unordered(_scan, args, chunksize=4):
            cheap_table[k] = c
            exc_table[k] = e
            done_mask[k] = True
            done += 1
            if done % 200 == 0:
                elapsed = time.time() - t0
                rt = (done - start_done) / elapsed if elapsed > 0 else 0
                eta = (n_pairs - done) / rt if rt > 0 else 0
                print(f"  {done}/{n_pairs} pairs  rate={rt:.1f}/s "
                      f"elapsed={elapsed/3600:.2f}h eta={eta/3600:.2f}h",
                      flush=True)
            if done - last_ckpt >= 1500:
                np.savez(CKPT, cheap_table=cheap_table, exc_table=exc_table,
                         done_mask=done_mask,
                         pair_list=np.array(pair_list, dtype=np.int32))
                last_ckpt = done
                print(f"  checkpoint @ {done}", flush=True)
    wall = time.time() - t0
    print(f"\nScan done in {wall:.0f}s ({wall/3600:.2f}h)", flush=True)

    for k, (i, j) in enumerate(pair_list):
        cheap_dense[i, j] = cheap_table[k]
        exc_dense[i, j] = exc_table[k]
    all_pairs = sorted(have | new_pairs)
    np.savez_compressed(OUT,
                        cheap=cheap_dense, exc=exc_dense,
                        t_starts=T_STARTS, tofs=TOFS,
                        pair_set=np.array(all_pairs, dtype=np.int32))
    print(f"Saved {OUT} ({len(all_pairs)} pairs total)", flush=True)
    new_finite = sum(1 for k in range(n_pairs)
                     if np.isfinite(cheap_table[k]).any()
                     or np.isfinite(exc_table[k]).any())
    print(f"New pairs with >=1 finite cell: {new_finite}/{n_pairs} "
          f"= {new_finite/n_pairs*100:.1f}%", flush=True)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
