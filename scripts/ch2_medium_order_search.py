"""E-731 — Ch2-MEDIUM order search to RECLAIM RANK-1 (target <186.27; bank 189.10 is a frozen-order artifact).

Faithful beam-retimer over the full-edge window table (cache/ch2_medium_windows.npz, no 0.025 tof floor) with the
<=5 exception budget, wrapped in or-opt/LNS over the visit ORDER (the frozen variable per E-731). Every accepted
candidate is FINAL-gated by the official kt.fitness. Positive control first: retime the bank order, confirm it is
~189.10 (the retimer must track the official DP, else the proxy is untrustworthy).
Usage: python ch2_medium_order_search.py [iters=200000] [K=6] [W=40] [maxwait=8]"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
import ch2_fast_transfer as ft
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/medium.kttsp")
kt = KTTSP(INST); OPAR = kt.opar.astype(np.float64)
THR = kt.dv_thr; EXC_THR = kt.dv_exc; NEXC = kt.n_exc; MAXREV = kt.max_revs
MINTOF = max(kt.min_tof, 0.01); MAXT = kt.max_time; DAY = 86400.0; N = kt.n
WIN = np.load(f"{ROOT}/cache/ch2_medium_windows.npz", allow_pickle=True)["windows"].item()
print(f"[E-731] medium n={N} dv_thr={THR} exc_thr={EXC_THR} n_exc={NEXC}; windows {len(WIN)} cheap edges", flush=True)


def cheap_arr(i, j, t, maxwait):
    """earliest cheap arrival on i->j departing in [t, t+maxwait] (lookup), else None."""
    w = WIN.get((i, j))
    if w is None:
        return None
    deps, tofs = w
    q = np.searchsorted(deps, t)
    if q < len(deps) and deps[q] <= t + maxwait:
        return float(deps[q] + tofs[q])
    return None


def exc_arr(i, j, t, maxwait):
    """earliest EXCEPTION arrival (dv<=EXC_THR) on i->j departing >= t (numba scan), else None. Used <=NEXC times."""
    deps = np.arange(t, min(t + maxwait + 8.0, MAXT), 0.25) * DAY
    tofs = ft.cheap_first_tof(OPAR[i], OPAR[j], deps, MINTOF * DAY, 6.0 * DAY, 0.05 * DAY, EXC_THR, MAXREV)
    m = tofs > 0
    if m.any():
        k = np.argmax(m)
        return float(deps[k] / DAY + tofs[k] / DAY)
    return None


def retime(order, K=6, W=40, maxwait=8.0):
    """forward beam retime with <=NEXC exceptions; returns (makespan, times, tofs, n_exc) or (inf,...). State =
    (arrival_time, exc_used). Keeps W states by (arrival, exc_used)."""
    states = [(0.0, 0, [], [])]                                # (t, exc_used, times_list, tofs_list) ; times=dep
    for p in range(len(order) - 1):
        i, j = order[p], order[p + 1]
        nxt = []
        for (t, eu, tl, fl) in states:
            w = WIN.get((i, j))
            if w is not None:
                deps, tofs = w; q = np.searchsorted(deps, t)
                if q < len(deps) and deps[q] <= t + maxwait:
                    dep = float(deps[q]); tof = float(tofs[q])
                    nxt.append((dep + tof, eu, tl + [dep], fl + [tof]))
            if eu < NEXC:                                      # also try an exception placement (branch)
                ea = exc_arr(i, j, t, maxwait)
                if ea is not None:
                    # recover dep,tof for the exception
                    dgrid = np.arange(t, min(t + maxwait + 8.0, MAXT), 0.25) * DAY
                    et = ft.cheap_first_tof(OPAR[i], OPAR[j], dgrid, MINTOF * DAY, 6.0 * DAY, 0.05 * DAY, EXC_THR, MAXREV)
                    mm = et > 0
                    if mm.any():
                        kk = int(np.argmax(mm)); dep = float(dgrid[kk] / DAY); tof = float(et[kk] / DAY)
                        nxt.append((dep + tof, eu + 1, tl + [dep], fl + [tof]))
        if not nxt:
            return float("inf"), None, None, NEXC + 1
        nxt.sort(key=lambda s: (s[0], s[1]))
        # dedup-ish: keep W best by arrival
        states = nxt[:W]
    best = min(states, key=lambda s: s[0])
    return best[0], best[2], best[3], best[1]


def official(order, times, tofs):
    dv = list(times) + list(tofs) + [float(c) for c in order]
    fit = kt.fitness(dv)
    return float(fit[0]), [float(x) for x in fit[1:]]


def main(iters=200000, K=6, W=40, maxwait=8.0):
    bank = np.array(json.load(open(f"{ROOT}/solutions/upload/medium.json"))[0]["decisionVector"])
    border = bank[2 * (N - 1):].astype(int).tolist()
    # POSITIVE CONTROL: retime the bank order, compare to official 189.10
    t0 = time.time()
    mk, ti, tf, eu = retime(border, K, W, maxwait)
    print(f"[E-731] POS-CONTROL bank order: retimer makespan {mk:.2f}d (exc {eu}) vs official 189.10 "
          f"[{time.time()-t0:.0f}s]", flush=True)
    if ti is not None:
        omk, ov = official(border, ti, tf)
        print(f"[E-731] bank order official re-score from retimer schedule: {omk:.2f}d viols {ov}", flush=True)
    # OR-OPT / LNS search
    rng = 20260627
    cur = border; cur_mk = mk; best = border; best_mk = mk; acc = 0
    ckpt = f"{ROOT}/cache/ch2_medium_ordersearch_best.json"
    for it in range(iters):
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        L = 1 + (rng % 3); a = 1 + (rng % (len(cur) - L - 1))
        seg = cur[a:a + L]; rest = cur[:a] + cur[a + L:]
        b = 1 + ((rng >> 8) % (len(rest) - 1))
        cand = rest[:b] + seg + rest[b:]
        cmk, cti, ctf, ceu = retime(cand, K, W, maxwait)
        if cmk < cur_mk or (rng % 25 == 0 and cmk < cur_mk + 1.0):
            cur, cur_mk = cand, cmk; acc += 1
        if cmk < best_mk - 1e-6 and cti is not None:
            omk, ov = official(cand, cti, ctf)               # FINAL gate
            if max(ov) <= 1e-6 and omk < 189.10:
                best, best_mk = cand, omk
                json.dump({"order": cand, "times": cti, "tofs": ctf, "makespan": omk},
                          open(ckpt, "w"))
                tag = "*** RANK-1 (<186.27)!" if omk < 186.27 else "better-than-bank"
                print(f"[E-731] it{it}: OFFICIAL {omk:.3f}d (retimer {cmk:.2f}) viols ok -> {tag} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
        if it % 500 == 0:
            print(f"[E-731] it{it}: cur {cur_mk:.2f} best {best_mk:.2f} acc {acc} [{time.time()-t0:.0f}s]",
                  flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(int(a[1]) if len(a) > 1 else 200000, int(a[2]) if len(a) > 2 else 6,
         int(a[3]) if len(a) > 3 else 40, float(a[4]) if len(a) > 4 else 8.0)
