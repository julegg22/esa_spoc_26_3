"""E-730 — Ch2-large: per-NODE structural + timing-fragility analysis to derive algorithmic priors.

User direction: mine the city graph for per-node features (connectivity, reachability, in/out cheap-degree,
timing fragility/robustness, feasible arrival-epoch windows) -> prioritise cities by fragility in the
constructor, and precompute "feasible arrival windows" as search priors. Also: how does short-tof connectivity
correlate with timing fragility?

Per giant city c we compute (from the faithful short-tof window table _FW):
  in_deg/out_deg   : # cheap predecessors / successors (connectivity)
  n_arr_win        : total cheap arrival windows into c
  arr_density      : fraction of 1-day bins in [0,460] where c is cheaply ARRIVABLE (timing robustness; high=robust)
  max_gap          : longest stretch (days) with NO cheap arrival window = TIMING FRAGILITY INDEX (high=fragile:
                     miss the window and you wait this long / strand)
  reach_out/in     : # cities reachable from / to c within 2 cheap hops (reachability)
Outputs: correlations (degree vs fragility), the fragile-city set, and saves per-node arrival-epoch sets +
a fragility-priority ordering to cache for the constructor.
"""
import sys, json, numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import importlib.util
spec = importlib.util.spec_from_file_location("cr", "/home/julian/Projects/esa_spoc_26_3/scripts/ch2_giant_completion_repair.py")
cr = importlib.util.module_from_spec(spec); spec.loader.exec_module(cr)
ROOT = "/home/julian/Projects/esa_spoc_26_3"
GID = set(cr.cities); FW = cr._FW
HORIZON = 460.0; BIN = 1.0

# arrival epochs into each city (clock-times at which c is cheaply reachable from SOME predecessor)
arr_ep = {c: [] for c in cr.cities}
indeg = {c: set() for c in cr.cities}; outdeg = {c: set() for c in cr.cities}
for (i, j), (deps, tofs) in FW.items():
    if i in GID and j in GID and len(deps) > 0:
        indeg[j].add(i); outdeg[i].add(j)
        arr_ep[j].extend((np.asarray(deps) + np.asarray(tofs)).tolist())


def features(c):
    a = np.array(sorted(e for e in arr_ep[c] if 0 <= e <= HORIZON))
    if len(a) == 0:
        return len(indeg[c]), len(outdeg[c]), 0, 0.0, HORIZON
    bins = np.floor(a / BIN).astype(int)
    density = len(set(bins.tolist())) / (HORIZON / BIN)
    # longest gap with no arrival window (include endpoints 0 and HORIZON)
    edges = np.concatenate(([0.0], a, [HORIZON]))
    max_gap = float(np.max(np.diff(edges)))
    return len(indeg[c]), len(outdeg[c]), len(a), density, max_gap


rows = {}
for c in cr.cities:
    rows[c] = features(c)
ind = np.array([rows[c][0] for c in cr.cities]); outd = np.array([rows[c][1] for c in cr.cities])
dens = np.array([rows[c][3] for c in cr.cities]); gap = np.array([rows[c][4] for c in cr.cities])


def corr(x, y):
    return float(np.corrcoef(x, y)[0, 1])


print(f"[E-730] {len(cr.cities)} giant cities. Feature distributions:")
for nm, v in [("in_deg", ind), ("out_deg", outd), ("arr_density", dens), ("max_gap(d)=FRAGILITY", gap)]:
    print(f"  {nm:22s} min {v.min():.2f}  p10 {np.percentile(v,10):.2f}  median {np.median(v):.2f}  "
          f"p90 {np.percentile(v,90):.2f}  max {v.max():.2f}")
print(f"\n[E-730] CORRELATIONS (the user's question — does connectivity predict timing fragility?):")
print(f"  in_deg     vs arr_density : {corr(ind,dens):+.3f}  (more cheap preds -> more robust arrival timing?)")
print(f"  in_deg     vs max_gap     : {corr(ind,gap):+.3f}  (low degree -> longer unreachable gaps = fragile?)")
print(f"  arr_density vs max_gap    : {corr(dens,gap):+.3f}")
print(f"  out_deg    vs in_deg      : {corr(outd,ind):+.3f}")

# fragility-priority ordering (most fragile first) + the fragile set
order = sorted(cr.cities, key=lambda c: (-rows[c][4], rows[c][3]))   # high max_gap first, then low density
FRAG = [c for c in cr.cities if rows[c][4] > np.percentile(gap, 80)]
print(f"\n[E-730] {len(FRAG)} cities above the 80th-pct fragility (max_gap > {np.percentile(gap,80):.1f}d) "
      f"= the timing-fragile set to place FIRST. Top-10 most fragile: {order[:10]}")
# overlap with the low-degree set
LOW = set(c for c in cr.cities if min(rows[c][0], rows[c][1]) <= 20)
ov = len(set(FRAG) & LOW)
print(f"[E-730] low-degree set |LOW|={len(LOW)}; fragile∩low-degree = {ov}/{len(FRAG)} "
      f"({100*ov/max(len(FRAG),1):.0f}% of fragile are also low-degree)")

json.dump({"fragility_order": [int(c) for c in order],
           "frag_set": [int(c) for c in FRAG],
           "arr_epochs": {str(c): sorted(round(e, 2) for e in arr_ep[c] if 0 <= e <= HORIZON) for c in cr.cities},
           "max_gap": {str(c): rows[c][4] for c in cr.cities},
           "arr_density": {str(c): rows[c][3] for c in cr.cities}},
          open(f"{ROOT}/cache/ch2_node_features.json", "w"))
print(f"\n[E-730] saved per-node arrival-epoch sets + fragility order -> cache/ch2_node_features.json (search prior)")
