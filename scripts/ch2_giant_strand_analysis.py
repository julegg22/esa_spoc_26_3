"""E-711 — Ch2-large rank-1: characterize the ~50 cities the time-aware beam STRANDS.

The fine-tof beam threads 540-558/601 then strands. Both wider W and exceptions failed to close the tail,
so the last ~50 are a structural 'hard shell'. Decisive question for the closer: WHEN are these cities
cheaply reachable? If their incoming cheap windows CLOSE EARLY (before the beam's makespan reaches them),
the fix is to FRONT-LOAD them (hard-shell-first construction), not wider search. Outputs the stranded set
+ their reachability-window stats so the next constructor can be designed, not guessed.
Usage: python ch2_giant_strand_analysis.py"""
import json, sys
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
ck = json.load(open(f"{ROOT}/cache/ch2_giant_fine_beam_best.json"))
visited = set(ck["path"]); mk = ck["t"]; depth = ck["depth"]
stranded = [c for c in cities if c not in visited]
print(f"[E-711] best partial: {depth}/{NG} visited, makespan {mk:.1f}d; {len(stranded)} stranded", flush=True)

# per-city reachability windows from the 1d table
from collections import defaultdict
in_rows = defaultdict(list); out_rows = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    in_rows[int(j)].append(r); out_rows[int(i)].append(r)


def reach_epochs(rows):
    """epochs where ANY of these edges is cheap (finite)."""
    if not rows:
        return None
    mask = FIN[rows].any(0)
    if not mask.any():
        return None
    es = EPOCHS[mask]
    return float(es.min()), float(es.max()), int(mask.sum())


def summarize(label, group):
    deadlines = []; opens = []; indeg = []
    for c in group:
        ri = reach_epochs(in_rows[c])
        if ri:
            opens.append(ri[0]); deadlines.append(ri[1]); indeg.append(len(in_rows[c]))
    if not deadlines:
        print(f"  [{label}] no reachability data", flush=True)
        return
    dl = np.array(deadlines); op = np.array(opens)
    print(f"  [{label}] n={len(group)} | in-window OPEN epoch: med {np.median(op):.0f} "
          f"| CLOSE(deadline) epoch: med {np.median(dl):.0f} p25 {np.percentile(dl,25):.0f} p75 {np.percentile(dl,75):.0f} "
          f"| in-deg med {int(np.median(indeg))}", flush=True)
    return dl


print("[E-711] reachability windows (epoch grid spans "
      f"{EPOCHS.min():.0f}..{EPOCHS.max():.0f}d; beam makespan {mk:.0f}d):", flush=True)
dl_strand = summarize("STRANDED", stranded)
summarize("visited", list(visited)[:300])

if dl_strand is not None:
    early = int((dl_strand < mk).sum())
    print(f"\n[E-711] of {len(stranded)} stranded, {early} have their LAST cheap-arrival epoch BEFORE the beam's "
          f"makespan ({mk:.0f}d) -> unreachable by the time the beam got there.", flush=True)
    if early > 0.5 * len(stranded):
        print(f"[E-711] -> VERDICT: hard-shell strands because windows CLOSE EARLY. The closer must FRONT-LOAD "
              f"them: reserve/visit hard-shell cities in their early windows first, then thread the easy core "
              f"around them (reserved-budget + subtour-bridge pattern). Wider forward beam cannot help.", flush=True)
    else:
        print(f"[E-711] -> stranded windows stay open late; stranding is a CHAINING failure, not a deadline one "
              f"-> bidirectional/insertion repair more promising than front-loading.", flush=True)
# persist the stranded set for the closer
json.dump({"stranded": stranded, "mk": mk, "depth": depth},
          open(f"{ROOT}/cache/ch2_giant_stranded.json", "w"))
print(f"[E-711] wrote stranded set -> cache/ch2_giant_stranded.json", flush=True)
