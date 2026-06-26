"""E-725b — Ch2-large rank-1: order-search on the NUMBA evaluator (E-725), with incremental suffix re-timing.

Unifies the frame fix (E-723 time-beam) + fast evaluator (E-725): per-edge cheap windows come from the numba
batched scanner (~1.6s/edge full 0-460 grid, cached) instead of the sparse 1d table + slow pykep fine-scan.
windows() is then an instant cache lookup. IncBeam re-times only the changed suffix. Strand-tolerant objective
(makespan + 50*strands) descends from a seed toward <425d & 0 strands = rank-1.
Usage: python ch2_giant_fast_search.py [seed_json] [W=40] [maxwait=120] [iters=500000] [tag=a]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
import ch2_fast_transfer as ft
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/hard.kttsp")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
kt = KTTSP(INST)
OPAR = kt.opar.astype(np.float64)
THR = kt.dv_thr; MAXREV = kt.max_revs; MINTOF = kt.min_tof; DAY = 86400.0
SP = 50.0
HORIZON = 460.0
DEPS = np.arange(0.0, HORIZON, 0.2)                              # departure grid (days)
DEPS_SEC = DEPS * DAY
TOF_LO, TOF_HI, TOF_STEP = max(MINTOF, 0.3), 13.0, 0.04          # tof scan (days)
_CACHE = {}                                                     # (i,j) -> (cheap_deps[], cheap_tofs[]) in days


def edge_windows(i, j):
    key = (i, j)
    c = _CACHE.get(key)
    if c is not None:
        return c
    tof = ft.cheap_first_tof(OPAR[i], OPAR[j], DEPS_SEC, TOF_LO * DAY, TOF_HI * DAY, TOF_STEP * DAY, THR, MAXREV)
    m = tof > 0
    c = (DEPS[m], tof[m] / DAY)
    _CACHE[key] = c
    return c


def windows(i, j, t, K, maxwait):
    deps, tofs = edge_windows(i, j)
    if len(deps) == 0:
        return []
    lo = np.searchsorted(deps, t); hi = np.searchsorted(deps, t + maxwait)
    out = []
    for q in range(lo, min(hi, len(deps))):
        out.append((deps[q], deps[q] + tofs[q]))
        if len(out) >= K:
            break
    return out


class IncBeam:
    def __init__(self, order, K, W, maxwait):
        self.order = list(order); self.K = K; self.W = W; self.mw = maxwait
        n = len(order)
        self.arr = [None] * n; self.scum = [0] * n
        self.arr[0] = [0.0]; self.scum[0] = 0
        _, _, cols = self._retime(self.order, 0); self.commit(self.order, 0, cols)

    def _retime(self, order, p):
        n = len(order); cur = self.arr[p]; scum = self.scum[p]; cols = []
        for q in range(p, n - 1):
            i, j = order[q], order[q + 1]; nxt = []
            for t in cur:
                for (dep, a) in windows(i, j, t, self.K, self.mw):
                    nxt.append(a)
            if not nxt:
                cur = [t + SP for t in cur]; scum += 1
            else:
                cur = sorted(set(round(x, 4) for x in nxt))[:self.W]
            cols.append((cur, scum))
        return cur[0], scum, cols

    def commit(self, order, p, cols):
        self.order = list(order)
        for off, (a, s) in enumerate(cols):
            self.arr[p + 1 + off] = a; self.scum[p + 1 + off] = s

    def current(self):
        return self.arr[-1][0], self.scum[-1]


def main(seed_json="bank", W=40, maxwait=120, iters=500000, tag="a"):
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    if seed_json == "bank":
        order = json.load(open(f"{ROOT}/cache/ch2_bank_giant_order.json"))
    else:
        obj = json.load(open(seed_json)); order = obj["order"] if isinstance(obj, dict) else obj
    order = [int(c) for c in order]; n = len(order)
    ft.transfer_dv(OPAR[0], OPAR[1], 10 * DAY, 1 * DAY, MAXREV)  # jit warmup
    t0 = time.time()
    ib = IncBeam(order, 4, W, maxwait)
    mk, st = ib.current(); best = mk + SP * st
    print(f"[E-725b-{tag}] seed: mk {mk:.1f}d strands {st} obj {best:.1f}; edges cached {len(_CACHE)} "
          f"[{time.time()-t0:.0f}s warmup]", flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_fast_search_best_{tag}.json"
    acc = 0; t_last = time.time(); it_last = 0
    for it in range(iters):
        cur = ib.order; new = list(cur)
        if rng.random() < 0.5:
            i = int(rng.integers(1, n - 2)); j = int(rng.integers(i + 1, min(n - 1, i + 80)))
            new[i:j] = new[i:j][::-1]; p = i - 1
        else:
            L = int(rng.integers(1, 4)); i = int(rng.integers(1, n - L - 1))
            seg = new[i:i + L]; del new[i:i + L]
            k = int(rng.integers(1, n - 1)); new[k:k] = seg; p = max(0, min(i, k) - 1)
        mk, st, cols = ib._retime(new, p); o = mk + SP * st
        if o < best:
            best = o; acc += 1; ib.commit(new, p, cols)
            json.dump({"order": ib.order, "makespan": mk, "strands": st}, open(CKPT, "w"))
            if st == 0 or it % 20 == 0:
                print(f"[E-725b-{tag}] it{it}: NEW best mk {mk:.1f}d strands {st} obj {best:.1f} acc={acc} "
                      f"[{time.time()-t0:.0f}s]", flush=True)
            if st == 0 and mk < 425:
                print(f"[E-725b-{tag}] *** {mk:.0f}d <425, 0 strands -> RANK-1 giant; stitch+verify+ESCALATE",
                      flush=True)
        if it % 500 == 0 and it > 0:
            rate = (it - it_last) / max(time.time() - t_last, 1e-9)
            print(f"[E-725b-{tag}] it{it}: best_mk {ib.current()[0]:.1f}d strands {ib.current()[1]} acc={acc} "
                  f"rate={rate:.2f} it/s edges={len(_CACHE)} [{time.time()-t0:.0f}s]", flush=True)
            t_last = time.time(); it_last = it
    print(f"[E-725b-{tag}] DONE best obj {best:.1f} acc={acc} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else "bank", int(a[2]) if len(a) > 2 else 40,
         int(a[3]) if len(a) > 3 else 120, int(a[4]) if len(a) > 4 else 500000, a[5] if len(a) > 5 else "a")
