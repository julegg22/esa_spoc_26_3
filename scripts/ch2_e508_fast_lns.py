"""E-508 — Massive LNS using fast table walker.

Once the fine table (/tmp/ch2_small_tcoupled_fine.npz) is ready:
  - Walk bank perm with fast table walker. Verify it gives mk close to 142.92.
  - Run 100k+ random 2-opt / or-opt iterations per worker (8 workers).
  - Track best feasible mk per worker; periodically validate top with full
    Lambert walk + UDP feasibility.

Variants: 2-opt, or-opt (relocate segment), reverse-segment, 4-opt double-bridge.

This uses the fine table for fast filtering AND fast scoring. Final
validation uses the full Lambert walk to ensure UDP feasibility.
"""
from __future__ import annotations
import sys, time, json, random
import numpy as np
import multiprocessing as mp
from pathlib import Path
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from esa_spoc_26.ch2_insert_lns import walk_perm_chrono
from ch2_fast_walker import fast_walk

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 2 "
        "Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
FINE_TABLE = '/tmp/ch2_small_tcoupled_fine.npz'

_GLOB = {}


def _init():
    _GLOB['kt'] = KTTSP(INST)
    d = np.load(FINE_TABLE)
    _GLOB['cheap'] = d['cheap']
    _GLOB['exc'] = d['exc']
    _GLOB['quantum'] = float(d['t_starts'][1] - d['t_starts'][0])
    _GLOB['n_exc'] = _GLOB['kt'].n_exc


def make_random_move(perm, rng):
    n = len(perm)
    mv_type = rng.choices(
        ['2opt', 'or_opt_1', 'or_opt_2', 'or_opt_3', 'swap'],
        weights=[3, 3, 2, 2, 1])[0]
    if mv_type == '2opt':
        i = rng.randint(1, n - 3)
        j = rng.randint(i + 1, n - 2)
        return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]
    elif mv_type.startswith('or_opt'):
        seg_len = int(mv_type[-1])
        if seg_len >= n - 2:
            return perm
        i = rng.randint(1, n - seg_len - 1)
        seg = perm[i:i+seg_len]
        rest = perm[:i] + perm[i+seg_len:]
        p = rng.randint(1, len(rest))
        return rest[:p] + seg + rest[p:]
    elif mv_type == 'swap':
        i = rng.randint(1, n - 2)
        j = rng.randint(1, n - 2)
        if i == j: return perm
        new = list(perm)
        new[i], new[j] = new[j], new[i]
        return new
    return perm


def lns_worker(args):
    seed, n_iters, T_max, init_mk, init_perm = args
    rng = random.Random(seed)
    cheap = _GLOB['cheap']
    exc = _GLOB['exc']
    quantum = _GLOB['quantum']
    n_exc = _GLOB['n_exc']
    cur_perm = list(init_perm)
    cur_mk = init_mk
    best_mk = init_mk
    best_perm = list(init_perm)
    t0 = time.time()
    last_log = t0
    n_walks = 0
    n_acc = 0
    n_feas = 0
    for it in range(n_iters):
        if time.time() - t0 > T_max:
            break
        cand = make_random_move(cur_perm, rng)
        if cand == cur_perm:
            continue
        mk, _td, _tof, exc_used, ok = fast_walk(
            cand, cheap, exc, quantum, n_exc_budget=n_exc)
        n_walks += 1
        if not ok:
            continue
        n_feas += 1
        # Acceptance: greedy by mk (no SA — could add)
        if mk < cur_mk:
            cur_mk = mk
            cur_perm = cand
            n_acc += 1
            if mk < best_mk:
                best_mk = mk
                best_perm = cand
        # Restart occasionally to escape local opt
        if it > 0 and it % 5000 == 0:
            # Random restart from best with extra kick
            for _ in range(5):
                cur_perm = make_random_move(best_perm, rng)
            mk, _, _, _, ok = fast_walk(
                cur_perm, cheap, exc, quantum, n_exc_budget=n_exc)
            cur_mk = mk if ok else best_mk
            if not ok:
                cur_perm = list(best_perm)
                cur_mk = best_mk
        if time.time() - last_log > 60:
            elapsed = time.time() - t0
            print(f"  [s={seed} it={it} t={elapsed:.0f}s] cur={cur_mk:.3f} "
                  f"best={best_mk:.3f} walks={n_walks} feas={n_feas} acc={n_acc} "
                  f"({n_walks/elapsed:.0f}/s)", flush=True)
            last_log = time.time()
    print(f"  [s={seed} DONE it={it} t={time.time()-t0:.0f}s] "
          f"best={best_mk:.3f} walks={n_walks} feas={n_feas} acc={n_acc}",
           flush=True)
    return seed, best_mk, best_perm, n_walks, n_acc


def main(n_workers=8, T_max=1800, n_iters=2000000):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE not ready at {FINE_TABLE}; aborting", flush=True)
        return
    kt = KTTSP(INST)
    bank = json.load(open(OUT))
    dv = bank[0]["decisionVector"]
    n = kt.n
    bank_perm = [int(x) for x in dv[2*(n-1):]]
    bank_times = list(dv[:n-1])
    bank_tofs = list(dv[n-1:2*(n-1)])
    bank_mk = bank_times[-1] + bank_tofs[-1]
    print(f"E-508: bank_mk={bank_mk:.4f}, target=R1=101.65", flush=True)

    # First: sanity-check fast walk on bank perm
    _init()
    fast_mk, _, _, _, ok = fast_walk(
        bank_perm, _GLOB['cheap'], _GLOB['exc'], _GLOB['quantum'],
        n_exc_budget=kt.n_exc)
    print(f"Bank perm fast walk: mk={fast_mk} ok={ok}", flush=True)
    init_mk = fast_mk if ok else 200.0
    if not ok:
        print("WARN: fast walk can't reproduce bank — use high init_mk",
              flush=True)
    init_perm = bank_perm

    args = [(s, n_iters, T_max, init_mk, init_perm) for s in range(n_workers)]
    t0 = time.time()
    best_overall = (init_mk, init_perm)
    with mp.Pool(n_workers, initializer=_init) as p:
        for seed, mk, perm, n_w, n_a in p.imap_unordered(lns_worker, args):
            if mk < best_overall[0]:
                best_overall = (mk, perm)
                print(f"  seed={seed}: NEW BEST {mk:.4f}d", flush=True)
    wall = time.time() - t0
    print(f"\nE-508 done in {wall:.0f}s", flush=True)
    print(f"Best fast-walker mk: {best_overall[0]:.4f}d", flush=True)

    # Validate best with full Lambert
    if best_overall[0] < init_mk:
        print(f"\n--- Full-Lambert validation of best perm ---", flush=True)
        best_lambert = None
        for ns, ws, wd in [(180, 12, 1.0), (360, 100, 0.1), (480, 200, 0.05)]:
            times, tofs, _dvs, ok, exc_w, _k = walk_perm_chrono(
                kt, best_overall[1], tof_window=18.0, n_steps=ns,
                wait_steps=ws, wait_dt=wd)
            if not ok: continue
            mk_l = times[-1] + tofs[-1]
            x = times + tofs + [float(p) for p in best_overall[1]]
            fit = kt.fitness(x)
            feas = kt.is_feasible(fit)
            print(f"  ns={ns} wd={wd}: mk={mk_l:.4f}d feas={feas}", flush=True)
            if feas and (best_lambert is None or mk_l < best_lambert[0]):
                best_lambert = (mk_l, x)

        if best_lambert and best_lambert[0] < 142.9183:
            bak = OUT + ".bak.20260530"
            if Path(OUT).exists() and not Path(bak).exists():
                Path(bak).write_bytes(Path(OUT).read_bytes())
                print(f"Backed up bank to {bak}", flush=True)
            Path(OUT).write_text(json.dumps([{
                "decisionVector": list(best_lambert[1]),
                "problem": "small",
                "challenge": CHALLENGE}]))
            print(f">>> BANKED: mk={best_lambert[0]:.4f}d "
                  f"({142.9183 - best_lambert[0]:.4f}d under bank)",
                   flush=True)
    return best_overall


if __name__ == "__main__":
    w = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    t = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    print(json.dumps(main(n_workers=w, T_max=t), default=str, indent=2))
