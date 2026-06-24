"""E-719b — Ch2-large rank-1: coverage-elite fine-tof beam (opportunistic rare-city capture).

E-719's deadline premise was REFUTED by the data: every periphery city's incoming cheap windows span the
FULL horizon (FIRSTDEP=0..LASTDEP=950 for all 120 indeg<40 cities) — they do NOT close early (E-664's claim
is wrong for this table). The real strand cause is SPARSE PHASE-ALIGNED REACHABILITY: periphery cities are
low in-degree, reachable across the horizon but only at sporadic, phase-dependent moments. The E-710 beam,
ranking states by EARLIEST ARRIVAL, commits to a frontier from which the remaining ~43 aren't reachable
*soon*, even though their windows are nominally open.

Fix (untried, distinct from E-711's failed GLOBAL rarity prune-key which derailed the core):
  (1) OPPORTUNISTIC CAPTURE — when at city i, also offer cheap edges to RARE (low-indeg) unvisited cities
      even if they aren't the earliest-arrival option, so a rare city reachable NOW is selectable;
  (2) COVERAGE-ELITE DIVERSITY — the next beam = union of (top W_core states by earliest t, preserving the
      core's rank-1 pace) and (top W_cov states by rare-cities-visited desc, preserving the branches that
      grabbed rare cities, which pure-t pruning kills). The core front stays untouched; coverage states are
      ADDED, not blended into the main ranking.
Reports the most-complete path + faithful makespan; checkpoints every 25 depths.
Usage: python ch2_giant_coverage_beam.py [W_core=70] [W_cov=40] [K=18] [thresh=40] [Radd=6] [start=-1]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
CKPT = f"{ROOT}/cache/ch2_giant_coverage_beam_best.json"
kt = KTTSP(INST)
d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz")
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
NG = len(cities)
OUT = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
GMIN = np.where(FIN.any(1), np.nanmin(np.where(FIN, VALS, np.inf), 1), np.inf)
for i in OUT:
    OUT[i].sort(key=lambda jr: GMIN[jr[1]])
INc = defaultdict(set)
for r, (i, j) in enumerate(KEYS):
    if FIN[r].any():
        INc[int(j)].add(int(i))
INDEG = {c: len(INc[c]) for c in cities}


def fine_cheap_arrival(i, j, row, t, dv_cap):
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 8)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if kt.compute_transfer(i, j, dep, float(tof)) <= dv_cap:
                return dep, float(tof), dep + float(tof)
    return None


def candidates(i, t, visited, K, exc_left, RARE, Radd):
    """Earliest-arrival cheap top-K (core), PLUS up to Radd cheap edges to RARE unvisited cities (offered
    even if not earliest), PLUS exceptions only when near-stuck."""
    out = []
    for (j, row) in OUT[i]:
        if j in visited:
            continue
        res = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if res is not None:
            out.append((j, res[2], res[1], 0))
            if len(out) >= K * 3:
                break
    out.sort(key=lambda c: c[1])
    out = out[:K]
    have = {c[0] for c in out}
    radded = 0                                                   # opportunistic: grab rare reachable-now cities
    for (j, row) in OUT[i]:
        if radded >= Radd:
            break
        if j in visited or j in have or j not in RARE:
            continue
        res = fine_cheap_arrival(i, j, row, t, kt.dv_thr)
        if res is not None:
            out.append((j, res[2], res[1], 0)); have.add(j); radded += 1
    if len([c for c in out if c[3] == 0]) < 4 and exc_left > 0:  # near-stuck -> exceptions
        for (j, row) in OUT[i][:40]:
            if j in visited or j in have:
                continue
            res = fine_cheap_arrival(i, j, row, t, kt.dv_exc)
            if res is not None:
                out.append((j, res[2], res[1], 1)); have.add(j)
                if sum(c[3] for c in out) >= 4:
                    break
    return out


def dedup_keep(states, key, n):
    """top-n by key, deduped by last-city (diversity)."""
    states = sorted(states, key=key)
    seen = set(); keep = []
    for s in states:
        if s["last"] in seen:
            continue
        seen.add(s["last"]); keep.append(s)
        if len(keep) >= n:
            break
    return keep


def main(W_core=70, W_cov=40, K=18, thresh=40, Radd=6, start=-1):
    RARE = set(c for c in cities if INDEG[c] < thresh)
    starts = [cities[start]] if start >= 0 else cities[:8]
    print(f"[E-719b] coverage beam W_core={W_core} W_cov={W_cov} K={K} thresh={thresh} (|RARE|={len(RARE)}) "
          f"Radd={Radd}; giant n={NG}; {len(starts)} seed(s)", flush=True)
    beam = [{"t": 0.0, "last": s, "vis": {s}, "path": [s], "exc": 0, "rare": int(s in RARE)} for s in starts]
    best = {"depth": 1, "path": list(beam[0]["path"]), "t": 0.0, "rare": beam[0]["rare"]}
    t0 = time.time(); pc = False
    for depth in range(1, NG):
        succ = []
        for st in beam:
            for (j, arr, tof, is_exc) in candidates(st["last"], st["t"], st["vis"], K, kt.n_exc - st["exc"], RARE, Radd):
                succ.append({"t": arr, "last": j, "vis": st["vis"] | {j}, "path": st["path"] + [j],
                             "exc": st["exc"] + is_exc, "rare": st["rare"] + (j in RARE)})
        if not pc:
            print(f"[E-719b] positive control: depth1 -> {len(succ)} successors "
                  f"({sum(s['rare'] for s in succ)} rare-capturing) [{time.time()-t0:.0f}s]", flush=True)
            pc = True
        if not succ:
            print(f"[E-719b] beam stranded at depth {depth}", flush=True)
            break
        core = dedup_keep(succ, lambda s: s["t"], W_core)                       # efficient-core front
        cov = dedup_keep(succ, lambda s: (-s["rare"], s["t"]), W_cov)           # coverage-elite front
        merged = {id(s): s for s in core}                                        # union (dedup by identity)
        for s in cov:
            merged[id(s)] = s
        beam = list(merged.values())
        deepest = max(beam, key=lambda s: len(s["path"]))
        # best = most cities; tie-break earliest time
        if (len(deepest["path"]), -deepest["t"]) > (best["depth"], -best["t"]):
            best = {"depth": len(deepest["path"]), "path": list(deepest["path"]), "t": deepest["t"],
                    "rare": deepest["rare"]}
        if depth % 20 == 0 or depth < 5:
            bt = min(beam, key=lambda s: s["t"]); mc = max(beam, key=lambda s: s["rare"])
            print(f"  depth {depth+1}: |beam|={len(beam)} best_depth={best['depth']} min_t={bt['t']:.1f}d "
                  f"(d/leg {bt['t']/max(len(bt['path'])-1,1):.3f}) | max_rare_in_beam={mc['rare']}/{len(RARE)} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
        if depth % 25 == 0:
            json.dump(best, open(CKPT, "w"))
    rin = sum(1 for c in best["path"] if c in RARE)
    print(f"\n[E-719b] DONE: deepest {best['depth']}/{NG}, makespan {best['t']:.1f}d "
          f"(d/leg {best['t']/max(best['depth']-1,1):.3f}); rare threaded {rin}/{len(RARE)}; "
          f"rank-1=424.62 (E-710 baseline 558@283d) [{time.time()-t0:.0f}s]", flush=True)
    json.dump(best, open(CKPT, "w"))
    if best["depth"] >= NG - 2 and best["t"] < 424.62:
        print(f"[E-719b] *** {best['depth']}/601 @ {best['t']:.0f}d < 424.62 -> RANK-1. "
              f"stitch satellites + udp verify + guard-bank + ESCALATE.", flush=True)
    elif best["depth"] > 558:
        print(f"[E-719b] {best['depth']}/601 (> E-710's 558) -> coverage-elite threads more; push params.", flush=True)
    else:
        print(f"[E-719b] {best['depth']}/601 (<= 558) -> coverage diversity didn't beat plain beam; "
              f"the all-601 path may need backward/meet-in-middle or it isn't beam-reachable.", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 70, int(a[2]) if len(a) > 2 else 40, int(a[3]) if len(a) > 3 else 18,
         int(a[4]) if len(a) > 4 else 40, int(a[5]) if len(a) > 5 else 6, int(a[6]) if len(a) > 6 else -1)
