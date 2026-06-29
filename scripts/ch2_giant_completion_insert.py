"""E-751 — Ch2-large completion-by-insertion (E-750 reframe). The forward beam threads a 546-city CHEAP comp0
core at 0.47 d/leg (a better backbone than the bank's order), but strands ~55 hard-shell cities; beam can't add
them (bidirectionally hard). The bank DOES visit all 601 — via expensive legs. So: take the cheap 546-core and
GRAFT the 55 missing comp0 cities by exact-clock cheapest-insertion (cheap leg if possible, else an exception
leg), then faithfully retime the complete 601-comp0 order. If its makespan beats the bank's comp0 portion (~804d
over 598 legs), the cheap backbone wins -> worth splicing into the full tour for a rank-2 push.
Usage: python ch2_giant_completion_insert.py"""
import sys, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_giant_lns_e742 as e
ROOT = e.ROOT; kt = e.kt; THR = e.THR; EXC = e.EXC


def retime(order, t0=0.0):
    """faithful retime: cheap leg if feasible else exception; returns (times,tofs,n_exc) or (None,k,_) on strand."""
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
    core = [int(c) for c in json.load(open(f"{ROOT}/cache/ch2_giant_fine_beam_546.json"))["path"]]
    comp0 = set(int(i) for ij in np.load(f"{ROOT}/cache/ch2_giant_faithful_windows.npz", allow_pickle=True)["windows"].item() for i in ij)
    missing = [c for c in comp0 if c not in set(core)]
    print(f"[E-751] cheap core {len(core)} cities, {len(missing)} missing of {len(comp0)} comp0", flush=True)
    res = retime(core)
    if res[0] is None:
        print(f"[E-751] core strands@{res[1]}", flush=True); return
    print(f"[E-751] core retime: {len(core)-1} legs, makespan {res[0][0][-1]+res[0][1][-1] if False else (np.array(res[0][0])+np.array(res[0][1])).max():.1f}d, {res[2]} exc", flush=True)
    order = list(core); t0 = time.time()
    # greedy cheapest-insertion: insert the missing city with the cheapest single best-gap, repeat
    for n in range(len(missing)):
        best = None                                              # (added_makespan, city, pos)
        rem = [c for c in missing if c not in set(order)]
        if not rem:
            break
        # current arrivals along order (epochs) for local scoring
        rr = retime(order)
        if rr[0] is None:
            print(f"[E-751] order strands@{rr[1]} after {n} inserts", flush=True); break
        ti, tf = rr[0]; arr = np.concatenate([[0.0], np.array(ti) + np.array(tf)])
        for c in rem[:40]:                                      # cap candidates per round for speed
            for p in range(1, len(order)):
                tdep = arr[p - 1]
                ra = e.earliest(order[p - 1], c, tdep, EXC)
                if ra is None:
                    continue
                rb = e.earliest(c, order[p], ra[2], EXC)
                if rb is None:
                    continue
                cost = (ra[1] + rb[1])                          # local added flight (approx)
                if best is None or cost < best[0]:
                    best = (cost, c, p)
        if best is None:
            print(f"[E-751] no insertable city left ({len(rem)} remain) after {n}", flush=True); break
        _, c, p = best; order.insert(p, c)
        if n % 10 == 0:
            print(f"[E-751] inserted {n+1}/{len(missing)} (city {c}@{p}) [{time.time()-t0:.0f}s]", flush=True)
    # final retime of the complete comp0 order
    rr = retime(order)
    if rr[0] is None:
        print(f"[E-751] FINAL order strands@{rr[1]} ({len(order)}/{len(comp0)} placed)", flush=True); return
    ti, tf = rr[0]; mk = float((np.array(ti) + np.array(tf)).max()); nexc = rr[2]
    print(f"[E-751] COMPLETE comp0 order: {len(order)}/{len(comp0)} cities, makespan {mk:.1f}d, {nexc} exception legs "
          f"[bank comp0 ~804d] [{time.time()-t0:.0f}s]", flush=True)
    json.dump({"order": [int(c) for c in order], "makespan": mk, "nexc": nexc},
              open(f"{ROOT}/cache/ch2_giant_completion_order.json", "w"))
    if mk < 804 and len(order) == len(comp0):
        print(f"[E-751] *** cheap-core backbone BEATS bank comp0 ({mk:.0f}<804) -> splice into full tour next", flush=True)
    else:
        print(f"[E-751] backbone {mk:.0f}d vs 804 (exc {nexc}) -> {'placed all' if len(order)==len(comp0) else 'incomplete'}", flush=True)


if __name__ == "__main__":
    main()
