"""E-506 — LNS over bank perm with time-coupled table as cheap filter.

Strategy:
  - Maintain best feasible perm (init: bank)
  - Random move: 2-opt (reverse [i..j]) OR or-opt (relocate segment [i..j] to position p)
  - CHEAP FILTER: walk the new perm using table (rewalk fn). If infeasible
    or makespan > current_best by more than 0.5d, skip the expensive walk.
  - Otherwise: walk with full Lambert (walk_perm_chrono) → real makespan.
    Accept if feasible AND makespan strictly < best.
  - Persist on improvement.

Compute budget: 10000 iterations or wall time T_max. Many workers in
parallel (one LNS per worker, different RNG seed).
"""
from __future__ import annotations
import sys, time, json, random
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from ch2_tcoupled_walk import load_tables, rewalk

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
CKP = "/tmp/ch2_e506_lns_ckpt.json"
_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)
    _GLOB['cheap'], _GLOB['exc'] = load_tables()


def two_opt(perm, i, j):
    if i >= j:
        return perm
    return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]


def or_opt(perm, i, j, p):
    """Relocate segment perm[i..j] to position p in remaining."""
    if i > j:
        return None
    seg = perm[i:j+1]
    rest = perm[:i] + perm[j+1:]
    if p < 0 or p > len(rest):
        return None
    return rest[:p] + seg + rest[p:]


def lns_worker(args):
    seed, n_iters, T_max, best_init = args
    kt = _GLOB['kt']
    cheap_tbl = _GLOB['cheap']
    exc_tbl = _GLOB['exc']
    rng = random.Random(seed)
    best_mk, best_perm = best_init
    best_x = None  # store full decision vector when found
    t0 = time.time()
    n_filtered = n_walked = n_accepted = 0
    n = len(best_perm)
    last_log = t0
    for it in range(n_iters):
        if time.time() - t0 > T_max:
            break
        # Random move type
        mv = rng.choice(['2opt', 'or_opt'])
        if mv == '2opt':
            i = rng.randint(1, n - 3)  # don't touch start
            j = rng.randint(i + 1, n - 2)
            cand = two_opt(best_perm, i, j)
        else:
            seg_len = rng.randint(1, min(4, n // 4))
            i = rng.randint(1, n - seg_len - 1)
            j = i + seg_len - 1
            p = rng.randint(1, n - seg_len)
            cand = or_opt(best_perm, i, j, p)
            if cand is None or cand == best_perm:
                continue
        # Table filter is too aggressive (bank itself fails) — skip it
        n_filtered += 1
        n_walked += 1
        # Full Lambert walk for true makespan
        times, tofs, dvs, ok_l, exc_l, _kl = walk_perm_chrono(
            kt, cand, tof_window=18.0, n_steps=180,
            wait_steps=12, wait_dt=1.0)
        if not ok_l:
            continue
        mk_l = times[-1] + tofs[-1]
        x = times + tofs + [float(p) for p in cand]
        fit = kt.fitness(x)
        if not kt.is_feasible(fit):
            continue
        if mk_l < best_mk - 0.001:
            best_mk = mk_l
            best_perm = list(cand)
            best_x = list(x)
            n_accepted += 1
        if time.time() - last_log > 30:
            elapsed = time.time() - t0
            print(f"  [seed={seed} it={it} t={elapsed:.0f}s] best={best_mk:.4f}  "
                  f"filt={n_filtered} walked={n_walked} accepted={n_accepted}",
                   flush=True)
            last_log = time.time()
    elapsed = time.time() - t0
    print(f"  [seed={seed} DONE it={it} t={elapsed:.0f}s] best={best_mk:.4f}  "
          f"filt={n_filtered} walked={n_walked} accepted={n_accepted}",
           flush=True)
    return seed, best_mk, best_perm, best_x, n_walked, n_accepted


def main(n_workers=6, T_max=1200, n_iters=100000):
    kt = KTTSP(INST)
    bank = json.load(open(OUT))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_times = list(dv[:n-1])
    bank_tofs = list(dv[n-1:2*(n-1)])
    bank_mk = bank_times[-1] + bank_tofs[-1]
    bank_x = list(dv)
    print(f"E-506 LNS: bank_mk={bank_mk:.4f}d, R3=111.76, R1=101.65",
           flush=True)
    print(f"Workers: {n_workers}, T_max={T_max}s, iters/worker={n_iters}",
           flush=True)
    args = [(s, n_iters, T_max, (bank_mk, bank_perm))
            for s in range(n_workers)]
    t0 = time.time()
    best_overall = (bank_mk, bank_perm, bank_x)
    with mp.Pool(n_workers, initializer=_init) as p:
        for seed, mk, perm, x, n_w, n_a in p.imap_unordered(lns_worker, args):
            if mk < best_overall[0]:
                best_overall = (mk, perm, x if x else bank_x)
                print(f"  seed={seed}: BEST mk={mk:.4f}d ({bank_mk - mk:.4f}d under bank)",
                       flush=True)
    wall = time.time() - t0
    print(f"\nE-506 complete: wall={wall:.0f}s", flush=True)
    print(f"Best mk: {best_overall[0]:.4f}d  (bank was {bank_mk:.4f}d)",
           flush=True)

    if best_overall[0] < bank_mk - 0.001 and best_overall[2]:
        # Bank update
        bak = OUT + ".bak.20260530"
        if Path(OUT).exists() and not Path(bak).exists():
            Path(bak).write_bytes(Path(OUT).read_bytes())
            print(f"Backed up bank to {bak}", flush=True)
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_overall[2]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: {OUT}  new mk={best_overall[0]:.4f}d",
               flush=True)
    return {"best_mk_d": best_overall[0], "wall_s": wall,
            "bank_prev_mk": bank_mk}


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    t = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
    print(json.dumps(main(n_workers=w, T_max=t), indent=2))
