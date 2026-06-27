"""E-735 probe #1 — Ch2-LARGE: the medium rank-1 machinery (faithful earliest-arrival walk + or-opt/2-opt order
search restricted to cheap edges, seeded from the COMPLETE existing tour) applied to comp0 (the 601-node giant
that holds ~876d of the 932d makespan). Tests A-FORWARD: is the 932 'reorder trap' a fixed-epoch-matrix artifact?

comp0-only canonical sub-problem: traverse all 601 comp0 cities starting at epoch T0, minimize finish time, using
the FAITHFUL fine-tof windows (cache/ch2_giant_faithful_windows.npz). Earliest-arrival walk is optimal for a fixed
order (waiting allowed + monotone arrival, E-589). Seed = the bank's own comp0 traversal order (already complete).
If or-opt/2-opt descends the finish time -> reorder lever is real (the trap was the method's, not reorder's).
Usage: CH2_T0=0 CH2_SEED=11 CH2_MOVE=oropt python ch2_giant_comp0_ordersearch.py [iters]"""
import os, sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
kt = KTTSP(INST)
T0 = float(os.environ.get("CH2_T0", "0"))
SEED = int(os.environ.get("CH2_SEED", "11"))
MOVE = os.environ.get("CH2_MOVE", "oropt")
TAG = os.environ.get("CH2_TAG", "c0")
ITERS = int(sys.argv[1]) if len(sys.argv) > 1 else 2_000_000

W = np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item()
# per-edge suffix-min earliest-arrival structures: for departures>=t, the min arrival (=dep+tof) and its dep/tof
EDGE = {}
ADJ = {}                                                         # cheap out-neighbours per city (for move legality)
for (i, j), (deps, tofs) in W.items():
    d = np.asarray(deps, dtype=float); tf = np.asarray(tofs, dtype=float)
    o = np.argsort(d); d = d[o]; tf = tf[o]; arr = d + tf
    sidx = np.empty(len(d), dtype=np.int64)
    if len(d):
        sidx[-1] = len(d) - 1
        for q in range(len(d) - 2, -1, -1):
            sidx[q] = q if arr[q] <= arr[sidx[q + 1]] else sidx[q + 1]
        EDGE[(i, j)] = (d, arr[sidx], d[sidx], tf[sidx])
        ADJ.setdefault(i, set()).add(j)
CITIES = sorted(set(i for ij in W for i in ij))
NC = len(CITIES)
print(f"[E-735][{TAG}] comp0 faithful windows: {len(EDGE)} directed edges, {NC} cities, T0={T0}", flush=True)


def walk(order, t0=T0):
    """faithful earliest-arrival walk; returns (finish_time, n_legs_done, times, tofs). strands -> n<len-1."""
    t = t0; nl = len(order) - 1
    times = np.empty(nl); tofs = np.empty(nl)
    for k in range(nl):
        e = EDGE.get((order[k], order[k + 1]))
        if e is None:
            return float("inf"), k, None, None
        d, smin, sdep, stof = e
        q = np.searchsorted(d, t)
        if q >= len(smin):
            return float("inf"), k, None, None
        times[k] = sdep[q]; tofs[k] = stof[q]; t = float(smin[q])
    return t, nl, times, tofs


def main():
    bank = json.load(open(f"{ROOT}/solutions/upload/large.json"))[0]["decisionVector"]
    N = 1051
    border = [int(c) for c in bank[2 * (N - 1):]]
    cset = set(CITIES)
    comp0_order = [c for c in border if c in cset]               # bank's comp0 cities in tour order (complete 601)
    print(f"[E-735][{TAG}] bank comp0 subsequence: {len(comp0_order)} cities (expect {NC})", flush=True)
    # POSITIVE CONTROL: walk the bank's comp0 order from T0
    t0 = time.time()
    fin, nl, ti, tf = walk(comp0_order)
    if nl < len(comp0_order) - 1:
        print(f"[E-735][{TAG}] POS-CTRL bank comp0 order STRANDS at leg {nl}/{len(comp0_order)-1} from T0={T0} "
              f"-> trying T0 at bank's first comp0 epoch", flush=True)
        # fall back: start at the epoch the bank actually enters comp0
        times = np.array(bank[:N - 1]); order = [int(c) for c in bank[2 * (N - 1):]]
        first = next(k for k, c in enumerate(order) if c in cset)
        fin, nl, ti, tf = walk(comp0_order, t0=float(times[first]))
        print(f"[E-735][{TAG}] retried from t={times[first]:.2f}: finish {fin:.2f}d legs {nl}/{len(comp0_order)-1}", flush=True)
    base = fin
    print(f"[E-735][{TAG}] POS-CTRL baseline comp0 finish={base:.2f}d ({nl}/{len(comp0_order)-1} legs, "
          f"{base/max(nl,1):.3f} d/leg) [{time.time()-t0:.0f}s]", flush=True)
    if not np.isfinite(base):
        print(f"[E-735][{TAG}] baseline infeasible from T0; abort (need a feasible complete seed)", flush=True); return

    def cheap_ok(*edges):
        return all((a in ADJ and b in ADJ[a]) for (a, b) in edges)

    cur = comp0_order; cur_fin = base; best = base; rng = SEED; acc = 0
    pbest = f"{ROOT}/cache/ch2_giant_comp0_best_{TAG}.json"
    for it in range(ITERS):
        cand = None
        for _try in range(40):
            rng = (rng * 1103515245 + 12345) & 0x7fffffff
            if MOVE == "2opt":
                a = 1 + (rng % (len(cur) - 3)); b = a + 2 + ((rng >> 8) % (len(cur) - a - 2))
                if cheap_ok((cur[a - 1], cur[b - 1]), (cur[a], cur[b])):
                    cand = cur[:a] + cur[a:b][::-1] + cur[b:]; break
            else:
                L = 1 + (rng % 3); a = 1 + (rng % (len(cur) - L - 1))
                seg = cur[a:a + L]; rest = cur[:a] + cur[a + L:]
                b = 1 + ((rng >> 8) % (len(rest) - 1))
                if cheap_ok((cur[a - 1], cur[a + L]), (rest[b - 1], seg[0]), (seg[-1], rest[b])):
                    cand = rest[:b] + seg + rest[b:]; break
        if cand is None:
            continue
        cf, cnl, cti, ctf = walk(cand)
        if cnl < len(cand) - 1:
            continue                                             # candidate strands -> reject
        if cf < cur_fin - 1e-9 or (rng % 30 == 0 and cf < cur_fin + 0.5):
            cur, cur_fin = cand, cf; acc += 1
        if cf < best - 1e-9:
            best = cf
            json.dump({"order": cand, "finish": cf, "t0": T0}, open(pbest, "w"))
            print(f"[E-735][{TAG}] it{it}: NEW BEST comp0 finish {cf:.2f}d ({cf/(len(cand)-1):.3f} d/leg) "
                  f"vs base {base:.2f} (-{base-cf:.1f}d) [{time.time()-t0:.0f}s]", flush=True)
        if it % 2000 == 0:
            print(f"[E-735][{TAG}] it{it}: cur {cur_fin:.2f} best {best:.2f} (base {base:.2f}) acc {acc} "
                  f"[{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    main()
