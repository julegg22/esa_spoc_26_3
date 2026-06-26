"""E-724 — Ch2-large rank-1: ORDER SEARCH for makespan compression, using the fine time-beam as evaluator.

The 2026-06-26 audit (E-723) fixed the frame: fixed-order time-beam on the full 0-950 graph + cached
fine-epoch fallback threads complete 601 orders (the bank order validates). Rank-1 (<425d) now requires
finding an ORDER whose time-beam makespan is low. This does greedy/SA descent on makespan over COMPLETE orders:
perturb (segment reverse / Or-opt relocate), re-time-beam, accept lower-makespan 0-strand tours. The fine-scan
cache (per edge) persists across iterations, so the evaluator warms up. Seed = a complete 601 order.
Usage: python ch2_giant_order_search.py [seed_json=bank] [W=60] [K=4] [maxwait=120] [iters=4000] [tag=a]"""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
os.environ.setdefault("CH2_TABLE", "/home/julian/Projects/esa_spoc_26_3/cache/ch2_giant_dense1d.npz")
import ch2_giant_timebeam as tb                                   # reuse windows + fine cache + timebeam
ROOT = "/home/julian/Projects/esa_spoc_26_3"


def main(seed_json="bank", W=60, K=4, maxwait=120, iters=4000, tag="a"):
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    if seed_json == "bank":
        order = json.load(open(f"{ROOT}/cache/ch2_bank_giant_order.json"))
    else:
        obj = json.load(open(seed_json)); order = obj["order"] if isinstance(obj, dict) else obj
    order = [int(c) for c in order]
    SPEN = 50.0
    def obj(o):
        mk, st, _ = tb.timebeam(o, K, W, maxwait, verbose=False, tolerate=True)
        return mk + SPEN * st, mk, st
    t0 = time.time()
    best, best_mk, best_st = obj(order)
    best_order = list(order)
    print(f"[E-724-{tag}] seed: makespan {best_mk:.1f}d strands {best_st} obj {best:.1f} (rank-1<425). "
          f"iters={iters} W={W} [{time.time()-t0:.0f}s warmup]", flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_order_search_best_{tag}.json"
    acc = 0
    for it in range(iters):
        new = list(best_order)
        if rng.random() < 0.5:                                    # segment reversal (2-opt)
            i = int(rng.integers(1, len(new) - 2)); j = int(rng.integers(i + 1, len(new) - 1))
            new[i:j] = new[i:j][::-1]
        else:                                                     # Or-opt: relocate a short segment
            L = int(rng.integers(1, 4)); i = int(rng.integers(1, len(new) - L - 1))
            seg = new[i:i + L]; del new[i:i + L]
            k = int(rng.integers(1, len(new) - 1)); new[k:k] = seg
        o, mk, st = obj(new)
        if o < best:                                              # accept lower (strands-then-makespan) objective
            best = o; best_mk = mk; best_st = st; best_order = new; acc += 1
            json.dump({"order": best_order, "makespan": best_mk, "strands": best_st}, open(CKPT, "w"))
            print(f"[E-724-{tag}] it{it}: NEW best mk {best_mk:.1f}d strands {best_st} obj {best:.1f} "
                  f"(acc={acc}) [{time.time()-t0:.0f}s]", flush=True)
            if best_st == 0 and best_mk < 425:
                print(f"[E-724-{tag}] *** {best_mk:.0f}d < 425, 0 strands -> RANK-1 giant; stitch+udp verify+"
                      f"guard-bank+ESCALATE", flush=True)
        if it % 25 == 0 and it > 0:
            print(f"[E-724-{tag}] it{it}: best mk {best_mk:.1f}d strands {best_st} acc={acc} "
                  f"[{time.time()-t0:.0f}s]", flush=True)
    print(f"[E-724-{tag}] DONE best mk {best_mk:.1f}d strands {best_st} acc={acc} [{time.time()-t0:.0f}s]",
          flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else "bank", int(a[2]) if len(a) > 2 else 60,
         int(a[3]) if len(a) > 3 else 4, int(a[4]) if len(a) > 4 else 120,
         int(a[5]) if len(a) > 5 else 4000, a[6] if len(a) > 6 else "a")
