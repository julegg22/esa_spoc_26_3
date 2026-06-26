"""E-726e — Ch2-large rank-1: randomized multi-start GRASP on the faithful short-tof window table.

The faithful beam (deterministic, 8 seeds) caps at ~191 (phasing corner-paint). Each faithful construction is
fast (~10s) now that windows are precomputed lookups. So run MANY randomized greedy constructions (randomized
restricted-candidate-list pick + random start) and keep the deepest — a cheap GRASP that may phase past 191
where the greedy front cannot. Keeps the best (most cities at lowest makespan). Reports + checkpoints.
Usage: python ch2_giant_faithful_grasp.py [iters=100000] [rcl=4] [maxwait=20] [tag=a]"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_faithful_beam as fb                              # reuse loaded window table + adjacency
ROOT = "/home/julian/Projects/esa_spoc_26_3"
cities = fb.cities; OUTADJ = fb.OUTADJ; earliest = fb.earliest


def construct(rng, rcl, maxwait):
    start = int(rng.choice(cities))
    vis = {start}; path = [start]; t = 0.0; last = start
    while True:
        cand = []
        for j in OUTADJ[last]:
            if j in vis:
                continue
            a = earliest(last, j, t, maxwait)
            if a is not None:
                cand.append((a, j))
                if len(cand) >= rcl * 4:
                    break
        if not cand:
            break
        cand.sort()
        pick = cand[int(rng.integers(0, min(rcl, len(cand))))]    # randomized among rcl earliest
        t, last = pick[0], pick[1]; vis.add(last); path.append(last)
    return path, t


def main(iters=100000, rcl=4, maxwait=20, tag="a"):
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    best_depth = 0; best = None; t0 = time.time()
    CKPT = f"{ROOT}/cache/ch2_giant_faithful_grasp_best_{tag}.json"
    for it in range(iters):
        path, mk = construct(rng, rcl, maxwait)
        if (len(path), -mk) > (best_depth, -(best[1] if best else 1e9)):
            best_depth = len(path); best = (path, mk)
            json.dump({"path": path, "makespan": mk, "depth": len(path)}, open(CKPT, "w"))
            print(f"[E-726e-{tag}] it{it}: NEW best depth {len(path)}/601 makespan {mk:.1f}d "
                  f"(d/leg {mk/max(len(path)-1,1):.3f}) [{time.time()-t0:.0f}s]", flush=True)
            if len(path) >= 599 and mk < 425:
                print(f"[E-726e-{tag}] *** {len(path)}/601 @ {mk:.0f}d < 425 -> RANK-1 candidate; verify+escalate",
                      flush=True)
        if it % 2000 == 0 and it > 0:
            print(f"[E-726e-{tag}] it{it}: best_depth {best_depth} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-726e-{tag}] DONE best_depth {best_depth} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 100000, int(a[2]) if len(a) > 2 else 4,
         int(a[3]) if len(a) > 3 else 20, a[4] if len(a) > 4 else "a")
