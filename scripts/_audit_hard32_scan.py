"""AUDIT (throwaway): exhaustive cheap in-edge scan for selected hard-32 cities.

For each target j, scan ALL source cities i over a FINE epoch grid (0.5d,
finer than the table's ~1d) and a fine tof grid, coarse-then-fine, count
distinct sources i with a cheap (<=dv_thr) incoming edge at any (epoch,tof).
Compare against the dense1d table's reported cheap in-sources.
"""
import sys, time, json
import numpy as np
import multiprocessing as mp
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
ROOT = '/home/julian/Projects/esa_spoc_26_3'
INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")

# FINER than table: table = 950 epochs over 0..950 (~1d) ; we use 0.5d.
EPOCHS = np.arange(0.0, 950.0 + 1e-9, 0.5)          # 1901 epochs, 0.5d
# FINER/WIDER tof than table (table: 0.02..2 x120, 2.1..8 x50 = max 8d)
TOFS = np.concatenate([np.linspace(0.02, 2.0, 100),
                       np.linspace(2.1, 8.0, 40),
                       np.linspace(8.5, 20.0, 24)])  # wider: up to 20d
COARSE = 8     # coarse prescan every 8th epoch (4d), fine +/-COARSE around hits
_K = {}


def _init():
    from esa_spoc_26.ch2_kttsp import KTTSP
    _K['kt'] = KTTSP(INST)


def _scan_cell(kt, i, j, t, thr):
    """min over tof at this epoch; return min dv (cheap-truncates early)."""
    best = np.inf
    for tof in TOFS:
        dv = kt.compute_transfer(i, j, float(t), float(tof))
        if dv < best:
            best = dv
        if best <= thr + 1e-6:
            return best
    return best


def _src_row(args):
    """For a fixed target j and source i, coarse-then-fine over epochs.
    Return (i, min_dv_found, found_cheap_bool)."""
    j, i = args
    kt = _K['kt']; thr = kt.dv_thr
    ne = len(EPOCHS)
    best = np.inf
    hits = []
    for ci in range(0, ne, COARSE):
        v = _scan_cell(kt, i, j, EPOCHS[ci], thr)
        if v < best:
            best = v
        if v <= thr + 1e-6:
            hits.append(ci)
            break  # cheap already proven for this source
    if best > thr + 1e-6:
        # refine around the best coarse epoch region (windows may sit between)
        ci_best = int(np.argmin([1]))  # placeholder
        # fine-scan around ALL coarse minima neighborhoods: do a full fine pass
        # only if coarse got "close" (<=2*thr) to avoid wasting time
        if best <= 2 * thr:
            for ci in range(0, ne, COARSE):
                lo = max(0, ci - COARSE); hi = min(ne, ci + COARSE + 1)
                for ek in range(lo, hi):
                    v = _scan_cell(kt, i, j, EPOCHS[ek], thr)
                    if v < best:
                        best = v
                    if best <= thr + 1e-6:
                        return i, float(best), True
    return i, float(best), bool(best <= thr + 1e-6)


def main():
    from esa_spoc_26.ch2_kttsp import KTTSP
    kt = KTTSP(INST)
    d = np.load(f'{ROOT}/cache/ch2_giant_dense1d.npz', allow_pickle=True)
    keys = d['keys']; vals = d['vals']; fin = np.isfinite(vals)
    edge_cheap = fin.any(axis=1)
    from collections import defaultdict
    tbl_in = defaultdict(set)
    for k in range(len(keys)):
        if edge_cheap[k]:
            tbl_in[int(keys[k, 1])].add(int(keys[k, 0]))
    cities = sorted(set(keys[:, 0]) | set(keys[:, 1]))

    targets = [477, 753, 532, 778, 846]   # ultra-low table in-deg
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    results = {}
    for j in targets:
        t0 = time.time()
        args = [(j, i) for i in cities if i != j]
        found = set(); mindvs = {}
        with mp.Pool(workers, initializer=_init) as p:
            for i, mdv, cheap in p.imap_unordered(_src_row, args, chunksize=8):
                mindvs[i] = mdv
                if cheap:
                    found.add(i)
        tbl = tbl_in[j]
        extra = found - tbl
        results[j] = {
            'table_in': len(tbl), 'scan_in': len(found),
            'extra_not_in_table': len(extra),
            'extra_sources_sample': sorted(extra)[:20],
            'min_dv_among_table_misses': round(min(
                (mindvs[i] for i in cities if i != j and i not in found),
                default=float('inf')), 1),
            'wall_min': round((time.time() - t0) / 60, 1),
        }
        print(f"city {j}: table_in={len(tbl)} scan_in={len(found)} "
              f"EXTRA={len(extra)} [{results[j]['wall_min']}min]", flush=True)
        json.dump(results, open(f'{ROOT}/cache/_audit_scan_results.json', 'w'),
                  indent=2)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
