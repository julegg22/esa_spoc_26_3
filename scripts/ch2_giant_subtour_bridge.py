"""E-722b — Ch2-large rank-1: sub-tour BRIDGE insertion (the Ch2-medium pattern, applied to the stranded cluster).

Diagnostic (E-722): the 564-tour's 37 missing cities are NOT the hard ones (median in-deg 41) — they're a
COHERENT, internally-connected CLUSTER, all enterable from the tour (32/37 from the first 200 cities). The
forward beam bypassed them and dead-ended at a frontier with 0 successors into the cluster. So this is pure
corner-painting, and the fix is a DETOUR: splice a time-dependent sub-tour through the cluster into the main
tour at a feasible point, instead of inserting cities one-by-one (which cascades, E-721g).

Method: retime the main 564-tour faithfully. For each candidate splice index p (sample across the tour), from
main[p] at time[p] run a greedy/beam path restricted to the missing cluster covering as many as feasible,
requiring the last detour city to cheaply reach main[p+1]; build the full tour main[:p+1]+detour+main[p+1:],
retime the suffix, score by (cities threaded, strands, makespan). The cheap windows are wide in EPOCH (E-721g),
so a uniform suffix delay should be largely absorbable. Best splice (or multi-splice) -> toward 601@<405d.
Usage: python ch2_giant_subtour_bridge.py [tour_json] [Wsub=30] [n_splice=40]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
from collections import defaultdict
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST); ktf = KTTSP(INST, max_revs=2)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d_aug.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
cities = sorted(set(KEYS[:, 0].tolist()) | set(KEYS[:, 1].tolist()))
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
OUT = defaultdict(list)
for r, (i, j) in enumerate(KEYS):
    OUT[int(i)].append((int(j), r))
SP = 50.0


def fine_arr(i, j, t):
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 9)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        if ktf.compute_transfer(i, j, dep, h) > 2.5 * kt.dv_thr:
            continue
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if ktf.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def retime(order):
    t = 0.0; strand = 0; times = [0.0]
    for k in range(len(order) - 1):
        r = fine_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += SP
        else:
            t = r
        times.append(t)
    return times, t, strand


def cluster_detour(start_city, t0, miss, target, Wsub):
    """from start_city at t0, beam through the missing cluster (cover as many as feasible), ending at a city
    that can cheaply reach `target`. Returns (detour_path_excluding_start, end_time) maximizing coverage."""
    beam = [{"t": t0, "last": start_city, "vis": set(), "path": []}]
    best = {"path": [], "t": t0, "cov": 0}
    for _ in range(len(miss)):
        succ = []
        for st in beam:
            for c in miss:
                if c in st["vis"]:
                    continue
                a = fine_arr(st["last"], c, st["t"])
                if a is not None:
                    succ.append({"t": a, "last": c, "vis": st["vis"] | {c}, "path": st["path"] + [c]})
        if not succ:
            break
        succ.sort(key=lambda s: (-len(s["path"]), s["t"]))
        seen = set(); beam = []
        for s in succ:
            if s["last"] in seen:
                continue
            seen.add(s["last"]); beam.append(s)
            if len(beam) >= Wsub:
                break
        for s in beam:                                            # track best that can rejoin to target
            if len(s["path"]) > best["cov"] and fine_arr(s["last"], target, s["t"]) is not None:
                best = {"path": list(s["path"]), "t": s["t"], "cov": len(s["path"])}
    return best


def main(tour_json=f"{ROOT}/cache/ch2_giant_reach_beam_w100_l1.0_c4.json", Wsub=30, n_splice=40):
    obj = json.load(open(tour_json))
    main_tour = obj["path"] if isinstance(obj, dict) else obj
    miss = [c for c in cities if c not in set(main_tour)]
    times, mk, st = retime(main_tour)
    print(f"[E-722b] main tour {len(main_tour)} cities, makespan {mk:.1f}d strands {st}; "
          f"cluster to bridge = {len(miss)}; Wsub={Wsub}", flush=True)
    # candidate splice points: sample across the tour (cluster reachable broadly; favor early where slack exists)
    cand_p = sorted(set(np.linspace(5, len(main_tour) - 2, n_splice).astype(int).tolist()))
    t0 = time.time()
    best_full = {"order": main_tour, "cov": 0, "mk": mk, "st": st}
    for ip, p in enumerate(cand_p):
        det = cluster_detour(main_tour[p], times[p], miss, main_tour[p + 1], Wsub)
        if det["cov"] == 0:
            continue
        new = main_tour[:p + 1] + det["path"] + main_tour[p + 1:]
        ntimes, nmk, nst = retime(new)
        threaded = len(new) - nst
        print(f"  splice@{p} (t={times[p]:.0f}d): detour covers {det['cov']}/{len(miss)} -> "
              f"tour {len(new)} cities, makespan {nmk:.1f}d strands {nst} (threaded {threaded}) "
              f"[{time.time()-t0:.0f}s]", flush=True)
        if (threaded, -nmk) > (len(best_full["order"]) - best_full["st"], -best_full["mk"]):
            best_full = {"order": new, "cov": det["cov"], "mk": nmk, "st": nst}
            json.dump({"order": new, "makespan": nmk, "strands": nst},
                      open(f"{ROOT}/cache/ch2_giant_subtour_bridge_best.json", "w"))
    threaded = len(best_full["order"]) - best_full["st"]
    print(f"\n[E-722b] BEST: {len(best_full['order'])} cities, threaded {threaded}, makespan "
          f"{best_full['mk']:.1f}d, strands {best_full['st']} [{time.time()-t0:.0f}s]", flush=True)
    if threaded >= 599 and best_full["mk"] < 405:
        print(f"[E-722b] *** {threaded} threaded @ {best_full['mk']:.0f}d < 405 -> RANK-1 candidate; "
              f"stitch satellites + udp verify + guard-bank + ESCALATE", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else f"{ROOT}/cache/ch2_giant_reach_beam_w100_l1.0_c4.json",
         int(a[2]) if len(a) > 2 else 30, int(a[3]) if len(a) > 3 else 40)
