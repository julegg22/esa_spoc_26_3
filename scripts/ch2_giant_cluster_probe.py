"""E-712 — Ch2-large rank-1: is the giant cluster-decomposable (the competitor's inferred paradigm)?

Forward beams (plain 540, rare-weighted 198) can't weave the sparse periphery; insertion completes only at
~800d. The remaining rank-1 lever is cluster+LKH. Foundation-first: characterize the orbital-element
clustering BEFORE building it. Key questions: (1) does the giant cluster cleanly by orbital elements?
(2) do the low-degree PERIPHERY cities land in well-connected clusters (absorb-able) or stay isolated
singletons (unhelpable)? (3) are clusters EPOCH-orderable (distinct cheap-window ranges -> chronological
concatenation viable)? Verdict gates whether cluster+LKH can reach rank-1 or the periphery is irreducibly hard.
Usage: python ch2_giant_cluster_probe.py [k=30]"""
import sys, json
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
giant = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
gset = set(giant)
indeg = defaultdict(int)
for (i, j) in KEYS:
    indeg[int(j)] += 1
# cheap adjacency within giant (any-epoch)
adj = defaultdict(set)
for r, (i, j) in enumerate(KEYS):
    if FIN[r].any():
        adj[int(i)].add(int(j))
# per-pair cheap-epoch midpoint (for epoch-ordering test)
emid = {}
for r, (i, j) in enumerate(KEYS):
    if FIN[r].any():
        es = EPOCHS[FIN[r]]; emid[(int(i), int(j))] = float(es.mean())


def main(k=30):
    opar = np.asarray(kt.opar)[giant]                              # (601,6) orbital elements
    X = (opar - opar.mean(0)) / (opar.std(0) + 1e-9)
    try:
        from sklearn.cluster import KMeans
        lab = KMeans(n_clusters=k, n_init=5, random_state=0).fit_predict(X)
    except ImportError:
        rng = np.random.default_rng(0); cen = X[rng.choice(len(X), k, replace=False)]
        for _ in range(25):
            lab = np.argmin(((X[:, None] - cen[None]) ** 2).sum(2), 1)
            cen = np.array([X[lab == c].mean(0) if (lab == c).any() else cen[c] for c in range(k)])
    g2c = {giant[i]: int(lab[i]) for i in range(len(giant))}
    clusters = defaultdict(list)
    for c, l in zip(giant, lab):
        clusters[int(l)].append(c)
    periph = [c for c in giant if indeg[c] < 40]
    print(f"[E-712] giant n={len(giant)}, k={k} orbital clusters; {len(periph)} periphery (in-deg<40)", flush=True)
    # (1)+(2): cluster sizes + intra-cluster connectivity + periphery placement
    intra_frac = []; periph_intra_deg = []
    for c, members in sorted(clusters.items()):
        ms = set(members)
        # intra-cluster cheap density
        e_in = sum(len(adj[u] & ms) for u in members)
        dens = e_in / max(1, len(members) * (len(members) - 1))
        intra_frac.append(dens)
    for p in periph:
        ms = set(clusters[g2c[p]])
        din = len(adj[p] & ms) + sum(1 for u in clusters[g2c[p]] if p in adj[u])  # intra in+out
        periph_intra_deg.append(din)
    sizes = sorted((len(m) for m in clusters.values()), reverse=True)
    print(f"  cluster sizes: {sizes[:12]}{'...' if len(sizes)>12 else ''}", flush=True)
    print(f"  intra-cluster cheap density: med {np.median(intra_frac):.2f} (vs giant global 0.127)", flush=True)
    pid = np.array(periph_intra_deg)
    print(f"  PERIPHERY intra-cluster degree: med {np.median(pid):.0f} | isolated(<2): {int((pid<2).sum())}/{len(periph)}", flush=True)
    # (3): epoch-orderability — does each cluster have a characteristic cheap-epoch?
    cl_epochs = {}
    for c, members in clusters.items():
        es = [emid[(u, v)] for u in members for v in adj[u] if (u, v) in emid]
        if es:
            cl_epochs[c] = (np.percentile(es, 25), np.median(es), np.percentile(es, 75))
    spreads = [hi - lo for (lo, _, hi) in cl_epochs.values()]
    print(f"  cluster cheap-epoch IQR-spread: med {np.median(spreads):.0f}d (horizon {EPOCHS.max():.0f}d) "
          f"-> {'distinct/orderable' if np.median(spreads) < 0.4*EPOCHS.max() else 'overlapping (hard to order)'}", flush=True)
    # verdict
    iso = int((pid < 2).sum())
    if iso < 0.2 * len(periph) and np.median(pid) >= 3:
        print(f"[E-712] -> VIABLE: periphery absorbs into clusters (med intra-deg {np.median(pid):.0f}, only {iso} isolated). "
              f"Build cluster+intra-fine-tof-TSP + epoch-ordered bridge. Rank-1 plausible.", flush=True)
    else:
        print(f"[E-712] -> periphery stays ISOLATED in clusters ({iso}/{len(periph)} singletons) -> clustering does NOT "
              f"absorb them; rank-1 periphery cost is irreducible by this paradigm. Large rank-1 likely needs the "
              f"competitor's exact cheap-graph or is a multi-day GTSP. Honest EV: low for the hours window.", flush=True)
    json.dump({giant[i]: int(lab[i]) for i in range(len(giant))}, open(f"{ROOT}/cache/ch2_giant_clusters.json", "w"))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
