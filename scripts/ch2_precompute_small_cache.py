"""Ch2-small ultrafine time-coupled table — REBUILD robust to cache/ (the E-526 table was /tmp-only and
got wiped). 0.05d quantum (sized so the bank's continuous schedule is representable — needed for the
CP-SAT bank-representability gate). Incremental save + RESUME (per feedback-persist-partials).

Output: cache/ch2_small_tcoupled_ultrafine.npz ; partial: cache/ch2_small_tcoupled_ultrafine.partial.npz
Usage: python ch2_precompute_small_cache.py [workers=4]"""
import sys, time, os
import numpy as np
import multiprocessing as mp
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 Keplerian "
        "Tomato Traveling Salesperson Problem/problems/easy.kttsp")
ROOT = "/home/julian/Projects/esa_spoc_26_3"
OUT = f"{ROOT}/cache/ch2_small_tcoupled_ultrafine.npz"
PARTIAL = f"{ROOT}/cache/ch2_small_tcoupled_ultrafine.partial.npz"
T_QUANTUM = 0.05
T_STARTS = np.arange(0.0, 200.0, T_QUANTUM)        # 4000
TOFS = np.linspace(0.025, 8.0, 160)
DV_CAP, DV_EXC = 100.0, 600.0
_KT = [None]


def _init():
    _KT[0] = KTTSP(INST)


def _scan(args):
    i, j = args; kt = _KT[0]
    cheap = np.full(len(T_STARTS), np.inf, np.float32); exc = np.full(len(T_STARTS), np.inf, np.float32)
    for ki, ts in enumerate(T_STARTS):
        if ts + 8.0 > kt.max_time:
            break
        for tof in TOFS:
            try:
                dv = kt.compute_transfer(i, j, float(ts), float(tof))
            except Exception:
                continue
            if dv <= DV_CAP:
                cheap[ki] = tof; exc[ki] = tof; break
            elif dv <= DV_EXC and tof < exc[ki]:
                exc[ki] = tof
    return i, j, cheap, exc


def main(workers=4):
    kt = KTTSP(INST); n = kt.n
    all_pairs = [(i, j) for i in range(n) for j in range(n) if i != j]
    cheap_t = np.full((n, n, len(T_STARTS)), np.inf, np.float32)
    exc_t = np.full((n, n, len(T_STARTS)), np.inf, np.float32)
    done = np.zeros((n, n), bool)
    if os.path.exists(PARTIAL):
        d = np.load(PARTIAL)
        cheap_t, exc_t, done = d["cheap"], d["exc"], d["done"]
        print(f"[RESUME] {int(done.sum())} pairs already scanned", flush=True)
    pairs = [(i, j) for (i, j) in all_pairs if not done[i, j]]
    print(f"[PRECOMPUTE] n={n}, {len(pairs)}/{len(all_pairs)} pairs to scan, T={len(T_STARTS)} q={T_QUANTUM}d, "
          f"workers={workers}", flush=True)
    # positive control: a known cheap pair should yield some finite cheap cells
    pc = _scan_with_init((0, 1))
    print(f"[PC] pair (0,1): {int(np.isfinite(pc[2]).sum())} cheap epochs (sanity: a graph edge exists somewhere)", flush=True)

    t0 = time.time(); cnt = 0
    os.makedirs(f"{ROOT}/cache", exist_ok=True)
    with mp.Pool(workers, initializer=_init) as p:
        for i, j, c, e in p.imap_unordered(_scan, pairs, chunksize=4):
            cheap_t[i, j] = c; exc_t[i, j] = e; done[i, j] = True; cnt += 1
            if cnt % 100 == 0:
                el = time.time() - t0; rate = cnt / el; eta = (len(pairs) - cnt) / rate
                print(f"  {cnt}/{len(pairs)} rate={rate:.1f}/s elapsed={el:.0f}s eta={eta/60:.0f}min", flush=True)
            if cnt % 200 == 0:
                np.savez_compressed(PARTIAL, cheap=cheap_t, exc=exc_t, done=done)
    np.savez_compressed(OUT, cheap=cheap_t, exc=exc_t, t_starts=T_STARTS, tofs=TOFS)
    nc = int(np.isfinite(cheap_t).sum()); tot = n * (n - 1) * len(T_STARTS)
    print(f"\n[PRECOMPUTE] DONE in {(time.time()-t0)/60:.0f}min. Saved {OUT}. "
          f"cheap cells {nc}/{tot} = {100*nc/tot:.2f}%", flush=True)
    if os.path.exists(PARTIAL):
        os.remove(PARTIAL)


def _scan_with_init(args):
    _init(); return _scan(args)


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    main(workers=w)
