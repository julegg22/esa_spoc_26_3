"""E-533 — Ch2 large (hard.kttsp): cheap-edge graph + component structure.

Quick structural diagnostic on large. For each directed pair (i, j),
probe 8 well-chosen (t, tof) cells. If any sample produces dv ≤ 100,
mark (i, j) as cheap. Compute connected components on the resulting
adjacency. Identify component sizes (expecting [601, 150, 150, 150]
per the existing component_aware module's claim).

Single-threaded by design (doesn't compete with E-531's 4-worker pool).
Estimated wall: 1-2 hours.

Probe samples (t, tof) — chosen to span the 3000 d horizon and the
useful tof range:
  (10, 1), (300, 3), (800, 5), (1500, 8), (2000, 2), (2500, 10),
  (100, 0.5), (1200, 4)
8 samples per pair × 1051² pairs × 0.55 ms ≈ 82 min on 1 core.

Outputs:
  /tmp/ch2_e533_large_adj.npz   — cheap_adj (bool n×n), exc_adj (bool n×n)
  vault/analysis/A-2026-06-07-ch2-large-structure.md (write-up)
"""
from __future__ import annotations
import sys, time
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/hard.kttsp")
OUT_ADJ = '/home/julian/Projects/esa_spoc_26_3/cache/ch2_e533_large_adj.npz'  # persistent (survives reboot)

# Sample (t, tof) probes — spread across horizon, varied tof magnitudes
PROBES = [
    (10.0, 1.0),
    (300.0, 3.0),
    (800.0, 5.0),
    (1500.0, 8.0),
    (2000.0, 2.0),
    (2500.0, 10.0),
    (100.0, 0.5),
    (1200.0, 4.0),
]
DV_CHEAP = 100.0
DV_EXC = 600.0


def main():
    kt = KTTSP(INST)
    n = kt.n
    print(f"E-533 large structure. n={n}, n_exc={kt.n_exc}, "
          f"max_time={kt.max_time}, probes={len(PROBES)}", flush=True)

    cheap_adj = np.zeros((n, n), dtype=bool)
    exc_adj = np.zeros((n, n), dtype=bool)
    out_deg_cheap = np.zeros(n, dtype=np.int32)
    in_deg_cheap = np.zeros(n, dtype=np.int32)

    t0 = time.time()
    n_calls = 0
    for i in range(n):
        for j in range(n):
            if i == j: continue
            best_dv = float('inf')
            for ts, tof in PROBES:
                try:
                    dv = kt.compute_transfer(i, j, ts, tof)
                    n_calls += 1
                    if dv < best_dv:
                        best_dv = dv
                    if dv <= DV_CHEAP:
                        break  # found cheap; no need to keep probing
                except Exception:
                    pass
            if best_dv <= DV_CHEAP:
                cheap_adj[i, j] = True
                exc_adj[i, j] = True
                out_deg_cheap[i] += 1
                in_deg_cheap[j] += 1
            elif best_dv <= DV_EXC:
                exc_adj[i, j] = True
        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate_pairs = (i + 1) * (n - 1) / elapsed
            eta = (n - i - 1) * (n - 1) / rate_pairs
            print(f"  row {i+1}/{n}  elapsed={elapsed/60:.1f}min "
                  f"pairs/s={rate_pairs:.0f} eta={eta/60:.1f}min "
                  f"calls={n_calls/1e6:.1f}M", flush=True)
    wall = time.time() - t0
    print(f"\nDetection done in {wall/60:.1f}min, {n_calls/1e6:.1f}M Lambert calls",
          flush=True)

    # Densities
    n_cheap = cheap_adj.sum()
    n_exc = exc_adj.sum() - n_cheap   # exc-only pairs
    print(f"\nDirected pair densities (probe-detected):")
    print(f"  cheap arcs (any t with dv≤100): {n_cheap}/{n*(n-1)} = "
          f"{n_cheap/(n*(n-1))*100:.2f}%", flush=True)
    print(f"  exc-only arcs (100<dv≤600):    {n_exc}/{n*(n-1)} = "
          f"{n_exc/(n*(n-1))*100:.2f}%", flush=True)

    # Components on UNDIRECTED cheap graph
    import scipy.sparse as sp
    import scipy.sparse.csgraph as csg
    adj_sym = cheap_adj | cheap_adj.T
    nc, lbl = csg.connected_components(sp.csr_matrix(adj_sym),
                                        directed=False)
    print(f"\nConnected components (cheap-edge, undirected): {nc}",
          flush=True)
    comp_sizes = [(int(lbl[lbl==c].size), c)
                  for c in range(nc)]
    comp_sizes.sort(reverse=True)
    print(f"  Top 10 by size: {[s for s, _ in comp_sizes[:10]]}",
          flush=True)
    print(f"  Total nodes in top-4 comps: "
          f"{sum(s for s, _ in comp_sizes[:4])}", flush=True)
    print(f"  Smallest comp sizes: {[s for s, _ in comp_sizes[-10:]]}",
          flush=True)

    # Per-comp boundary node analysis: high in/out degree nodes
    print(f"\nTop-4 component details:")
    for rank, (sz, c) in enumerate(comp_sizes[:4]):
        members = np.where(lbl == c)[0]
        # internal cheap arcs only
        int_out = sum(out_deg_cheap[v] for v in members)
        # high-out nodes (bridge candidates)
        sorted_by_out = sorted(members, key=lambda v: -out_deg_cheap[v])
        top5_out = [(int(v), int(out_deg_cheap[v])) for v in sorted_by_out[:5]]
        sorted_by_in = sorted(members, key=lambda v: -in_deg_cheap[v])
        top5_in = [(int(v), int(in_deg_cheap[v])) for v in sorted_by_in[:5]]
        print(f"  comp_rank={rank} size={sz}", flush=True)
        print(f"    top-out-deg nodes (high out-bridge potential): {top5_out}",
              flush=True)
        print(f"    top-in-deg nodes (high in-bridge potential):   {top5_in}",
              flush=True)

    # Save adj + labels
    np.savez_compressed(OUT_ADJ, cheap=cheap_adj, exc=exc_adj,
                        labels=lbl, out_deg=out_deg_cheap,
                        in_deg=in_deg_cheap)
    print(f"\nSaved {OUT_ADJ}", flush=True)


if __name__ == '__main__':
    main()
