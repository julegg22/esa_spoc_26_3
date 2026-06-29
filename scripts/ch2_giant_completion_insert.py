"""E-751 — Ch2-large completion-by-insertion (FAST: dense1d scoring + one faithful retime). The 546 cheap-core
retimes to 255.5d/0-exc (0.47 d/leg) vs bank comp0 804d (1.35). Graft the 55 missing comp0 cities by greedy
cheapest-insertion scored with the precomputed dense1d min-cheap-tof per edge (instant), then ONE faithful
THR-then-EXC retime of the complete 601-order. DECISIVE measurement = the EXCEPTION-LEG COUNT: kttsp allows only
5 total. If the 33 bidirectionally-hard cities (E-750) need >>5 exception legs, the cheap backbone cannot be
legally completed -> bank's expensive-leg routing is necessary -> large rank-2 is hard-shell-bound.
Usage: python ch2_giant_completion_insert.py"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_lns_e742 as e
ROOT = e.ROOT; kt = e.kt; THR = e.THR; EXC = e.EXC
BIG = 9e9


def retime(order, t0=0.0):
    nl = len(order) - 1; times = np.empty(nl); tofs = np.empty(nl); t = t0; nexc = 0
    for k in range(nl):
        r = e.earliest(order[k], order[k + 1], t, THR)
        if r is None:
            r = e.earliest(order[k], order[k + 1], t, EXC)
            if r is None:
                return None, k, nexc
            nexc += 1
        times[k] = r[0]; tofs[k] = r[1]; t = r[2]
    return (times, tofs), nl, nexc


def main():
    t0 = time.time()
    d = np.load(f"{ROOT}/cache/ch2_giant_dense1d.npz"); K = d["keys"]; V = d["vals"]
    mt = {}                                                       # (i,j) -> min cheap tof over epochs (optimistic)
    vmin = np.where(np.isfinite(V), V, np.inf).min(axis=1)
    for r in range(len(K)):
        if np.isfinite(vmin[r]):
            mt[(int(K[r][0]), int(K[r][1]))] = float(vmin[r])
    core = [int(c) for c in json.load(open(f"{ROOT}/cache/ch2_giant_fine_beam_546.json"))["path"]]
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)
    missing = [c for c in comp0 if c not in set(core)]
    print(f"[E-751] core {len(core)}, missing {len(missing)}; dense1d {len(mt)} cheap edges [{time.time()-t0:.0f}s]", flush=True)

    def gapcost(a, c, b):
        return mt.get((a, c), BIG) + mt.get((c, b), BIG) - mt.get((a, b), 0.0)

    order = list(core)
    # insert easiest-first: each round pick the (city,gap) with min gapcost
    placed = 0
    while missing:
        best = None
        for c in missing:
            for p in range(1, len(order)):
                cc = gapcost(order[p - 1], c, order[p])
                if best is None or cc < best[0]:
                    best = (cc, c, p)
        _, c, p = best; order.insert(p, c); missing.remove(c); placed += 1
        if placed % 15 == 0:
            print(f"[E-751] inserted {placed}/55 (cost {best[0]:.3f}) [{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-751] all 55 inserted -> {len(order)} cities; faithful retime... [{time.time()-t0:.0f}s]", flush=True)
    rr = retime(order)
    if rr[0] is None:
        print(f"[E-751] FINAL retime STRANDS@{rr[1]} [{time.time()-t0:.0f}s]", flush=True); return
    ti, tf = rr[0]; mk = float((np.array(ti) + np.array(tf)).max()); nexc = rr[2]
    json.dump({"order": [int(c) for c in order], "makespan": mk, "nexc": nexc},
              open(f"{ROOT}/cache/ch2_giant_completion_order.json", "w"))
    print(f"[E-751] COMPLETE comp0 {len(order)}/601: makespan {mk:.1f}d, {nexc} EXCEPTION legs "
          f"[bank comp0 804d; budget=5 TOTAL incl bridges] [{time.time()-t0:.0f}s]", flush=True)
    if nexc <= 4 and mk < 804:                                    # <=4 leaves room for bridges within budget 5
        print(f"[E-751] *** FEASIBLE-CANDIDATE: cheap backbone {mk:.0f}d, {nexc} exc -> SPLICE into full tour", flush=True)
    elif mk < 804:
        print(f"[E-751] cheap backbone {mk:.0f}<804 BUT {nexc} exception legs >> budget 5 -> "
              f"the hard-shell cities need exception legs the bank also pays; cheap core not legally completable. "
              f"Large rank-2 is hard-shell-bound.", flush=True)
    else:
        print(f"[E-751] backbone {mk:.0f}>=804, no gain", flush=True)


if __name__ == "__main__":
    main()
