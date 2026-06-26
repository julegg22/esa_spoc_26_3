"""E-724b — Ch2-large rank-1: order-search with INCREMENTAL suffix re-timing (faster evaluator).

E-724 was ~6min/traverse (full time-beam per perturbation) -> too slow. A perturbation at position p leaves the
prefix [0:p] timing unchanged, so we cache per-position beam states (arrivals list + cumulative strands) and
re-time only from p. Reversal [i,j] -> p=i; relocate(i->k) -> p=min(i,k). Bias perturbations to span less of the
tail so the average re-time is short. Same fine-epoch evaluator (E-723) via the timebeam module.
Usage: python ch2_giant_order_search_inc.py [seed_json] [W=40] [K=4] [maxwait=120] [iters=200000] [tag=a]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
os.environ.setdefault("CH2_TABLE", "/home/julian/Projects/esa_spoc_26_3/cache/ch2_giant_dense1d.npz")
import ch2_giant_timebeam as tb
ROOT = "/home/julian/Projects/esa_spoc_26_3"
SP = 50.0


class IncBeam:
    """maintains arrivals[] and cumulative-strands[] per position for the current order; re-times only the
    changed suffix on each candidate."""
    def __init__(self, order, K, W, maxwait):
        self.order = list(order); self.K = K; self.W = W; self.mw = maxwait
        n = len(order)
        self.arr = [None] * n; self.scum = [0] * n
        self.arr[0] = [0.0]; self.scum[0] = 0
        _, _, cols = self._retime(self.order, 0)
        self.commit(self.order, 0, cols)

    def _retime(self, order, p):
        """re-time positions p..n-1 for `order` starting from cached arr[p]; return (makespan, strands, newcols)
        where newcols is the list of (arrivals, scum) for positions p+1..n-1 (to commit on accept)."""
        n = len(order)
        cur = self.arr[p]; scum = self.scum[p]
        cols = []
        for q in range(p, n - 1):
            i, j = order[q], order[q + 1]
            nxt = []
            for t in cur:
                for (dep, a) in tb.windows(i, j, t, self.K, self.mw):
                    nxt.append(a)
            if not nxt:
                cur = [t + SP for t in cur]; scum += 1
            else:
                cur = sorted(set(round(x, 4) for x in nxt))[:self.W]
            cols.append((cur, scum))
        mk = cur[0]
        return mk, scum, cols

    def commit(self, order, p, cols):
        self.order = list(order)
        for off, (a, s) in enumerate(cols):
            self.arr[p + 1 + off] = a; self.scum[p + 1 + off] = s

    def current(self):
        return self.arr[-1][0], self.scum[-1]


def main(seed_json="bank", W=40, K=4, maxwait=120, iters=200000, tag="a"):
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    if seed_json == "bank":
        order = json.load(open(f"{ROOT}/cache/ch2_bank_giant_order.json"))
    else:
        obj = json.load(open(seed_json)); order = obj["order"] if isinstance(obj, dict) else obj
    order = [int(c) for c in order]
    n = len(order)
    t0 = time.time()
    ib = IncBeam(order, K, W, maxwait)
    mk, st = ib.current(); best = mk + SP * st
    print(f"[E-724b-{tag}] seed: makespan {mk:.1f}d strands {st} obj {best:.1f} [{time.time()-t0:.0f}s warmup]",
          flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_order_search_inc_best_{tag}.json"
    acc = 0; t_last = time.time(); it_last = 0
    for it in range(iters):
        cur_order = ib.order
        new = list(cur_order)
        if rng.random() < 0.5:
            i = int(rng.integers(1, n - 2)); j = int(rng.integers(i + 1, min(n - 1, i + 60)))   # bounded reversal
            new[i:j] = new[i:j][::-1]; p = i - 1                  # last UNCHANGED position (arr[p] still valid)
        else:
            L = int(rng.integers(1, 4)); i = int(rng.integers(1, n - L - 1))
            seg = new[i:i + L]; del new[i:i + L]
            k = int(rng.integers(1, n - 1)); new[k:k] = seg; p = max(0, min(i, k) - 1)
        mk, st, cols = ib._retime(new, p)
        o = mk + SP * st
        if o < best:
            best = o; acc += 1; ib.commit(new, p, cols)
            json.dump({"order": ib.order, "makespan": mk, "strands": st}, open(CKPT, "w"))
            if it % 5 == 0 or st == 0:
                print(f"[E-724b-{tag}] it{it}: NEW best mk {mk:.1f}d strands {st} obj {best:.1f} (acc={acc}) "
                      f"[{time.time()-t0:.0f}s]", flush=True)
            if st == 0 and mk < 425:
                print(f"[E-724b-{tag}] *** {mk:.0f}d <425, 0 strands -> RANK-1 giant; stitch+verify+ESCALATE",
                      flush=True)
        if it % 200 == 0 and it > 0:
            rate = (it - it_last) / max(time.time() - t_last, 1e-9)
            print(f"[E-724b-{tag}] it{it}: best_mk {ib.current()[0]:.1f}d strands {ib.current()[1]} acc={acc} "
                  f"rate={rate:.1f} it/s [{time.time()-t0:.0f}s]", flush=True)
            t_last = time.time(); it_last = it
    print(f"[E-724b-{tag}] DONE best obj {best:.1f} acc={acc} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else "bank", int(a[2]) if len(a) > 2 else 40,
         int(a[3]) if len(a) > 3 else 4, int(a[4]) if len(a) > 4 else 120,
         int(a[5]) if len(a) > 5 else 200000, a[6] if len(a) > 6 else "a")
