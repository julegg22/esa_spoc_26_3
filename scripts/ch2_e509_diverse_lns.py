"""E-509 — Diverse-seed LNS with broader validation.

Differences from E-508:
  - Each worker starts from a DIFFERENT permutation (varied seeds: bank,
    greedy_findxfer from multiple start nodes, random shuffles, etc.).
  - Workers collect 200+ top perms each (vs 50).
  - Validates top 1000 unique perms with full Lambert (vs 100).
  - Longer run (45 min).

Goal: find perms with structurally different fast-walker mk regimes; hope
that Lambert variance + diversity uncovers a >1d improvement.
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
from esa_spoc_26.ch2_findtransfer_greedy import greedy_findxfer
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


def make_seed_perms():
    """Generate diverse starting perms: bank + greedy_findxfer(start=k) for k=[34, 0, 10, 23] + random shuffles."""
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(OUT))
    bank_perm = [int(x) for x in bank[0]["decisionVector"][2*(n-1):]]
    seeds = {'bank': bank_perm}

    # 4 random shuffles
    rng = random.Random(2026)
    for k in range(4):
        p = list(range(n))
        rng.shuffle(p)
        seeds[f'rand_{k}'] = p
    # 4 starts via greedy_findxfer
    for start_node in (34, 0, 10, 18):
        try:
            perm, _t, _tf, _dv, ok = greedy_findxfer(
                kt, start=start_node, tof_window=18.0,
                n_steps=180, wait_steps=12, wait_dt=1.0)
            if ok and len(perm) == n:
                seeds[f'greedy_{start_node}'] = list(perm)
            else:
                # fallback: shuffle starting at start_node
                p = [start_node] + [j for j in range(n) if j != start_node]
                rng.shuffle(p[1:])
                seeds[f'shuf_{start_node}'] = p
        except Exception:
            pass
    return list(seeds.items())


def make_random_move(perm, rng):
    n = len(perm)
    mv_type = rng.choices(
        ['2opt', 'or_opt_1', 'or_opt_2', 'or_opt_3', 'swap', 'double_bridge'],
        weights=[3, 2, 2, 2, 1, 1])[0]
    if mv_type == '2opt':
        i = rng.randint(1, n - 3); j = rng.randint(i + 1, n - 2)
        return perm[:i] + perm[i:j+1][::-1] + perm[j+1:]
    elif mv_type.startswith('or_opt'):
        seg_len = int(mv_type[-1])
        if seg_len >= n - 2: return perm
        i = rng.randint(1, n - seg_len - 1)
        seg = perm[i:i+seg_len]
        rest = perm[:i] + perm[i+seg_len:]
        p = rng.randint(1, len(rest))
        return rest[:p] + seg + rest[p:]
    elif mv_type == 'swap':
        i = rng.randint(1, n - 2); j = rng.randint(1, n - 2)
        if i == j: return perm
        new = list(perm); new[i], new[j] = new[j], new[i]; return new
    elif mv_type == 'double_bridge':
        # 4 random cuts (a < b < c < d), rearrange [d:] + [b:c] + [c:d] + [a:b] + [:a]
        if n < 8: return perm
        cuts = sorted(rng.sample(range(1, n-1), 3))
        a, b, c = cuts
        return perm[:a] + perm[c:] + perm[b:c] + perm[a:b]
    return perm


def lns_worker(args):
    seed_id, seed_perm, T_max = args
    rng = random.Random(hash(seed_id) % (2**31))
    cheap = _GLOB['cheap']; exc = _GLOB['exc']
    quantum = _GLOB['quantum']; n_exc = _GLOB['n_exc']
    walk_kwargs = {'n_exc_budget': n_exc, 'window_q': 300,
                   'exc_policy': 'cheap_unless_infeasible'}

    init_fmk, _, _, _, ok0 = fast_walk(seed_perm, cheap, exc, quantum,
                                        **walk_kwargs)
    if not ok0:
        init_fmk = 220.0
    cur_perm = list(seed_perm)
    cur_mk = init_fmk
    best_mk = init_fmk
    best_perm = list(seed_perm)
    top_perms = []  # all feasible (mk, perm) seen
    t0 = time.time()
    last_log = t0
    n_walks = n_acc = n_feas = 0
    T = 8.0
    T_min = 0.3
    T_decay = 0.9998
    it = 0
    while time.time() - t0 < T_max:
        it += 1
        cand = make_random_move(cur_perm, rng)
        if cand == cur_perm:
            continue
        mk, _td, _tof, exc_used, ok = fast_walk(cand, cheap, exc, quantum,
                                                  **walk_kwargs)
        n_walks += 1
        if not ok:
            continue
        n_feas += 1
        # Always track promising perms
        if mk < init_fmk + 20:  # within 20d of seed best
            top_perms.append((mk, list(cand)))
        delta = mk - cur_mk
        if delta < 0 or rng.random() < (2.718 ** (-delta / max(T, 0.1))):
            cur_mk = mk
            cur_perm = cand
            n_acc += 1
            if mk < best_mk:
                best_mk = mk
                best_perm = list(cand)
        T = max(T_min, T * T_decay)
        if it > 0 and it % 10000 == 0:
            # Restart
            cur_perm = list(best_perm); cur_mk = best_mk
            T = 8.0
        if time.time() - last_log > 90:
            elapsed = time.time() - t0
            print(f"  [{seed_id} it={it} t={elapsed:.0f}s] cur={cur_mk:.2f} "
                  f"best={best_mk:.2f} walks={n_walks} feas={n_feas} "
                  f"top={len(top_perms)} ({n_walks/elapsed:.0f}/s)",
                   flush=True)
            last_log = time.time()
    elapsed = time.time() - t0
    print(f"  [{seed_id} DONE it={it} t={elapsed:.0f}s] best={best_mk:.2f} "
          f"top_collected={len(top_perms)}", flush=True)
    return seed_id, best_mk, best_perm, top_perms


def main(T_max=2400, workers=8):
    if not Path(FINE_TABLE).exists():
        print(f"FINE TABLE missing at {FINE_TABLE}; abort", flush=True)
        return
    kt = KTTSP(INST)
    n = kt.n
    bank_mk = 142.8913
    print(f"E-509: bank={bank_mk:.4f}d  R3=111.76  R1=101.65", flush=True)
    seeds = make_seed_perms()
    print(f"Seeds: {[s[0] for s in seeds]}", flush=True)

    # Use min(workers, len(seeds)) workers
    n_w = min(workers, len(seeds))
    seeds = seeds[:n_w]

    args = [(sid, sp, T_max) for sid, sp in seeds]
    t0 = time.time()
    all_top = []
    best_overall = (1e9, None)
    with mp.Pool(n_w, initializer=_init) as p:
        for seed_id, mk, perm, top_perms in p.imap_unordered(lns_worker, args):
            print(f"  --- worker {seed_id}: best fmk={mk:.2f} "
                  f"({len(top_perms)} candidates) ---", flush=True)
            all_top.extend(top_perms)
            if mk < best_overall[0]:
                best_overall = (mk, perm)
    wall = time.time() - t0
    print(f"\nE-509 LNS done in {wall:.0f}s. all_top: {len(all_top)}",
           flush=True)

    # Dedup and sort
    seen = set()
    uniq = []
    for mk, p in sorted(all_top, key=lambda x: x[0]):
        key = tuple(p)
        if key in seen: continue
        seen.add(key); uniq.append((mk, p))
    print(f"Unique perms: {len(uniq)}. fmk range: "
          f"{uniq[0][0]:.2f} - {uniq[-1][0]:.2f}", flush=True)

    # Validate top 1500 with multiple Lambert configs
    K = min(1500, len(uniq))
    print(f"\n--- Validating top {K} perms with Lambert ---", flush=True)
    best_lambert = None
    n_better_than_bank = 0
    t_val = time.time()
    last_print = t_val
    for ix, (fmk, perm) in enumerate(uniq[:K]):
        best_for_perm = None
        for ns, ws, wd in [(180, 12, 1.0), (360, 60, 0.2)]:
            times, tofs, _, ok, _, _ = walk_perm_chrono(
                kt, perm, tof_window=18.0, n_steps=ns,
                wait_steps=ws, wait_dt=wd)
            if not ok: continue
            mk_l = times[-1] + tofs[-1]
            x = times + tofs + [float(p) for p in perm]
            fit = kt.fitness(x)
            if kt.is_feasible(fit):
                if best_for_perm is None or mk_l < best_for_perm[0]:
                    best_for_perm = (mk_l, x)
        if best_for_perm is None:
            continue
        if best_for_perm[0] < bank_mk:
            n_better_than_bank += 1
        if best_lambert is None or best_for_perm[0] < best_lambert[0]:
            best_lambert = best_for_perm
            print(f"  [{ix:4d}] fmk={fmk:.2f} → lambert={best_for_perm[0]:.4f}d  "
                  f"{'UNDER BANK' if best_for_perm[0] < bank_mk else ''}",
                   flush=True)
        if time.time() - last_print > 60:
            elapsed = time.time() - t_val
            print(f"  ... [{ix}/{K}] elapsed={elapsed:.0f}s best={best_lambert[0]:.4f}",
                   flush=True)
            last_print = time.time()
    print(f"\nValidation wall: {time.time() - t_val:.0f}s",
           flush=True)
    print(f"Perms beating bank: {n_better_than_bank}/{K}", flush=True)
    if best_lambert and best_lambert[0] < bank_mk:
        # Bank update
        bak_old = OUT + ".bak.20260530"
        bak_new = OUT + ".bak.20260530.v2"
        if Path(OUT).exists() and not Path(bak_new).exists():
            Path(bak_new).write_bytes(Path(OUT).read_bytes())
        Path(OUT).write_text(json.dumps([{
            "decisionVector": list(best_lambert[1]),
            "problem": "small",
            "challenge": CHALLENGE}]))
        print(f">>> BANKED: mk={best_lambert[0]:.4f}d  "
              f"({bank_mk - best_lambert[0]:.4f}d under prev bank)", flush=True)


if __name__ == "__main__":
    tm = int(sys.argv[1]) if len(sys.argv) > 1 else 2400
    main(T_max=tm)
