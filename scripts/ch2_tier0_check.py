"""Ch2-small Tier-0 CHECK (2026-06-22): does the exception-reallocation lever have headroom?
Identify the bank's 5 exception legs (official dv in (100,600]), classify each as an inter-component
BRIDGE (structurally required) vs WITHIN-component (a reallocation candidate), and measure each one's
ToF (its direct makespan cost). If the within-component exceptions are short, Tier 0 is low-value."""
import sys, json
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
BANK = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
kt = KTTSP(INST); n = kt.n
x = np.array(json.load(open(BANK))[0]["decisionVector"], float)
times = x[:n - 1]; tofs = x[n - 1:2 * (n - 1)]; order = [round(v) for v in x[2 * (n - 1):]]

# cheap-edge components (from the 2026-05-30 audit); comp0 = everything else
COMPS = {1: {4, 11, 17}, 2: {16, 27, 32}, 3: {18, 23, 34}}
def comp_of(c):
    for k, s in COMPS.items():
        if c in s:
            return k
    return 0

mk = times[-1] + tofs[-1]
print(f"[TIER0] bank makespan = {mk:.4f} d (rank-3 target 110.88 -> need -{mk-110.88:.2f}d)", flush=True)
print(f"[TIER0] dv_thr={kt.dv_thr} dv_exc={kt.dv_exc} n_exc={kt.n_exc}", flush=True)

legs = []
for i in range(n - 1):
    a, b = order[i], order[i + 1]
    dv = kt.compute_transfer(a, b, float(times[i]), float(tofs[i]))
    legs.append((i, a, b, dv, float(tofs[i])))
exc = [L for L in legs if L[3] > kt.dv_thr + 1e-6]
cheap_tof = sum(L[4] for L in legs if L[3] <= kt.dv_thr + 1e-6)
print(f"[TIER0] {len(exc)} exception legs (dv>{kt.dv_thr}); Σtof cheap legs={cheap_tof:.2f}d, "
      f"Σtof exc legs={sum(L[4] for L in exc):.2f}d", flush=True)
print("\n  leg  a -> b    dv(m/s)   tof(d)   type", flush=True)
bridge_tof = within_tof = 0.0; n_bridge = n_within = 0
for (i, a, b, dv, tf) in sorted(exc, key=lambda L: -L[4]):
    ca, cb = comp_of(a), comp_of(b)
    kind = f"BRIDGE comp{ca}->comp{cb}" if ca != cb else f"WITHIN comp{ca}"
    if ca != cb:
        bridge_tof += tf; n_bridge += 1
    else:
        within_tof += tf; n_within += 1
    print(f"  {i:3d}  {a:2d} -> {b:2d}   {dv:7.1f}  {tf:6.3f}   {kind}", flush=True)

print(f"\n[TIER0] bridges: {n_bridge} (Σtof {bridge_tof:.2f}d, structurally required to join 4 comps, need >=3)", flush=True)
print(f"[TIER0] within-component exceptions: {n_within} (Σtof {within_tof:.2f}d = the reallocation headroom CEILING)", flush=True)
print(f"[TIER0] VERDICT: Tier-0 upside is bounded by ~{within_tof:.2f}d of within-comp exception ToF "
      f"vs the {mk-110.88:.2f}d needed for rank-3.", flush=True)
