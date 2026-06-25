"""E-721e — Ch2-large rank-1: faithful time-dependent SA / global re-order (the completion lever).

Local insertion cascades (E-721d); a feasible COMPLETE tour + SA descent on the FAITHFUL makespan is the
right frame — every move re-times globally, so the cascade is correctly SCORED, not avoided. The prior SA
basin-locked at 909 using a COARSE table; the new ingredients are the FINE (compute_transfer-verified)
makespan + the recovered graph. Seed = a feasible complete 601 order (the bank giant order, feasible at full
horizon on the original table). Moves: or-opt (relocate a 1-3 segment) + 2-opt (reverse a segment). SA accept
on makespan. Fine retime ~0.8s/move.
Usage: python ch2_giant_tdsa.py [seed_json] [iters=40000] [T0=40] [tag=a]
Env CH2_TABLE: original 0-950 (feasible for the 913d bank) | aug/clean (recovered, lower horizon)."""
import sys, json, time, os
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch2_kttsp import KTTSP
ROOT = "/home/julian/Projects/esa_spoc_26_3"
INST = "reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp"
kt = KTTSP(INST); ktf = KTTSP(INST, max_revs=2)
d = np.load(os.environ.get("CH2_TABLE", f"{ROOT}/cache/ch2_giant_dense1d.npz"))
EPOCHS = d["epochs"]; KEYS = d["keys"]; VALS = d["vals"]; FIN = np.isfinite(VALS)
PIDX = {(int(i), int(j)): r for r, (i, j) in enumerate(KEYS)}
STRAND_PEN = 50.0
rng = np.random.default_rng(0)


def fine_arr(i, j, t):
    row = PIDX.get((i, j))
    if row is None:
        return None
    e0 = np.searchsorted(EPOCHS, t)
    for e in range(max(0, e0 - 1), min(len(EPOCHS), e0 + 9)):
        if not FIN[row, e]:
            continue
        dep = max(t, float(EPOCHS[e])); h = float(VALS[row, e])
        for tof in np.arange(max(kt.min_tof, h - 0.025), h + 0.025, 0.0005):
            if ktf.compute_transfer(i, j, dep, float(tof)) <= kt.dv_thr:
                return dep + float(tof)
    return None


def makespan(order):
    t = 0.0; strand = 0
    for k in range(len(order) - 1):
        r = fine_arr(order[k], order[k + 1], t)
        if r is None:
            strand += 1; t += STRAND_PEN
        else:
            t = r
    return t, strand


def or_opt(order):
    n = len(order); L = int(rng.integers(1, 4))
    i = int(rng.integers(0, n - L)); seg = order[i:i + L]
    rest = order[:i] + order[i + L:]
    j = int(rng.integers(0, len(rest)))
    return rest[:j] + seg + rest[j:]


def two_opt(order):
    n = len(order); i = int(rng.integers(0, n - 2)); j = int(rng.integers(i + 2, n))
    return order[:i] + order[i:j][::-1] + order[j:]


def main(seed_json, iters=40000, T0=40.0, tag="a"):
    global rng
    rng = np.random.default_rng(abs(hash(tag)) % (2 ** 31))
    order = json.load(open(seed_json))
    if isinstance(order, dict):
        order = order.get("order") or order.get("path")
    order = [int(c) for c in order]
    t0 = time.time()
    mk, st = makespan(order); cur = mk + STRAND_PEN * st
    best = cur; best_order = list(order); best_mk = mk; best_st = st
    print(f"[TDSA-{tag}] seed {len(order)} cities, makespan {mk:.1f}d strands {st}; iters={iters} T0={T0}", flush=True)
    CKPT = f"{ROOT}/cache/ch2_giant_tdsa_best_{tag}.json"
    acc = 0
    for it in range(iters):
        T = T0 * (0.9998 ** it) + 0.1
        new = or_opt(order) if rng.random() < 0.6 else two_opt(order)
        nmk, nst = makespan(new); nc = nmk + STRAND_PEN * nst
        if nc < cur or rng.random() < np.exp(-(nc - cur) / max(T, 1e-6)):
            order = new; cur = nc; acc += 1
            if nc < best:
                best = nc; best_order = list(new); best_mk = nmk; best_st = nst
                json.dump({"order": best_order, "makespan": best_mk, "strands": best_st}, open(CKPT, "w"))
                if best_st == 0 and best_mk < 405:
                    print(f"[TDSA-{tag}] *** 601 @ {best_mk:.1f}d, 0 strands (full <424 RANK-1) it{it} "
                          f"-> verify+stitch+escalate", flush=True)
        if it % 50 == 0:
            print(f"[TDSA-{tag}] it{it}: cur {cur:.0f} best_mk {best_mk:.1f}d best_strands {best_st} "
                  f"T={T:.1f} acc={acc} [{time.time()-t0:.0f}s]", flush=True)
    print(f"[TDSA-{tag}] DONE best_mk {best_mk:.1f}d strands {best_st} [{time.time()-t0:.0f}s]", flush=True)


if __name__ == "__main__":
    a = sys.argv
    main(a[1] if len(a) > 1 else f"{ROOT}/cache/ch2_bank_giant_order.json",
         int(a[2]) if len(a) > 2 else 40000, float(a[3]) if len(a) > 3 else 40.0, a[4] if len(a) > 4 else "a")
