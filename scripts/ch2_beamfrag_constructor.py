"""E-730b — Ch2-large: W>1 time-aware BEAM constructor from fragility-ranked starts.

The W=1 greedy fragstart seed = 87 strands; branching over windows (don't commit to a stranding phase) + keeping
the deepest-then-earliest states = 44 strands (best seed yet, start 491). This sweeps starts to minimise the
seed strand-count, saving the best to cache/ch2_seed_beamfrag.json for the CLS fleet.
Usage: python ch2_beamfrag_constructor.py [n_starts=20] [K=3] [W=30] [maxwait=12]"""
import sys, json, time
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import importlib.util
spec = importlib.util.spec_from_file_location("cr", "/home/julian/Projects/esa_spoc_26_3/scripts/ch2_giant_completion_repair.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.ft.transfer_dv(m.OPAR[0], m.OPAR[1], 10 * m.DAY, 1 * m.DAY, m.MAXREV)
ROOT = "/home/julian/Projects/esa_spoc_26_3"
nf = json.load(open(f"{ROOT}/cache/ch2_node_features.json")); FRAG_ORDER = nf["fragility_order"]
GID = set(m.cities); SUCC = {c: sorted(m.OUTADJ[c] & GID) for c in m.cities}


def beam_construct(start, maxwait, K, W):
    beam = [(0.0, start, frozenset([start]), (start,))]
    bestpath = beam[0][3]
    for _ in range(len(m.cities) - 1):
        nxt = []
        for (t, last, vis, path) in beam:
            cnt = 0
            for j in SUCC[last]:
                if j in vis:
                    continue
                w = m.windows_k(last, j, t, 1, maxwait)
                if w:
                    nxt.append((w[0], j, vis | {j}, path + (j,))); cnt += 1
                    if cnt >= K:
                        break
        if not nxt:
            break
        nxt.sort(key=lambda s: (-len(s[3]), s[0]))
        seen = set(); keep = []
        for s in nxt:
            if s[1] in seen:
                continue
            seen.add(s[1]); keep.append(s)
            if len(keep) >= W:
                break
        beam = keep
        if len(beam[0][3]) > len(bestpath):
            bestpath = beam[0][3]
    path = list(bestpath); vis = set(path)
    for c in FRAG_ORDER:                                        # complete by appending unvisited (dead-ends)
        if c not in vis:
            path.append(c)
    return path


def main(n_starts=20, K=3, W=30, maxwait=12.0):
    t0 = time.time(); best = None
    for s in FRAG_ORDER[:n_starts]:
        o = beam_construct(s, maxwait, K, W)
        mk, st, _ = m.retime_tol(o, maxwait, K=3, W=16)
        if best is None or st < best[1]:
            best = (s, st, mk, o)
            json.dump({"path": [int(c) for c in o], "strands": st, "makespan": mk},
                      open(f"{ROOT}/cache/ch2_seed_beamfrag.json", "w"))
            print(f"  start {s}: NEW best strands {st} mk {mk:.0f}d [{time.time()-t0:.0f}s]", flush=True)
    print(f"DONE beam best strands {best[1]} from start {best[0]} (greedy fragstart=87) [{time.time()-t0:.0f}s]",
          flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 20, int(a[2]) if len(a) > 2 else 3,
         int(a[3]) if len(a) > 3 else 30, float(a[4]) if len(a) > 4 else 12.0)
