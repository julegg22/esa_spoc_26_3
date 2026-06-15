"""E-618 — Ch2 small: GRASP multi-start (independent from-scratch construction).

Why this, and why now (2026-06-15, after E-617 ILS firmed the local null):
  Decomposition of the 112.996 bank: travel 105.7d (93.5%), idle 7.29d (6.5%),
  5 exc legs are express shortcuts (tof 0.4-0.8d vs cheap median 2.0d). So the
  gap to R1 (101.65) is PURE TRAVEL — a shorter-tof PERMUTATION, not timing.
  E-617 ILS proved the bank is an ISOLATED optimum: 13.8k local
  perturbation+repair attempts, its entire 3-7-node neighborhood is >1% worse.
  The local-descent family (E-529 SA, E-617 ILS) is exhausted.

  The one untested family is INDEPENDENT construction: build whole tours from
  scratch with a randomized-greedy (GRASP) restricted candidate list, sampling
  DIFFERENT permutation basins the deterministic greedy (which built the bank)
  never reaches. The bank was found by deterministic earliest-arrival greedy +
  LNS; GRASP explores the orderings that greedy's argmin pruned away.

  Construction runs on the precomputed ultrafine table (cheap/exc tof per epoch
  bucket) — same edge model as the DP evaluator, so a constructed tour's greedy
  makespan and its DP makespan are consistent. Each constructed permutation is
  DP-polished for its true optimum schedule, guard-banked if < 112.996.

This is the basin-overarching test the campaign thesis calls for. If thousands
of independent randomized constructions + DP-polish still cannot beat 112.996,
Ch2-small's gap to R1 is a genuine free-method floor (the structure is too
constrained — 33/49 nodes have <=2 cheap edges, routing is near-forced).

Usage: python ch2_e618_grasp_multistart.py [n_workers=4] [wall_h=24] [rcl=3]
"""
from __future__ import annotations
import sys, os, json, time, random, math
from pathlib import Path
import numpy as np
import multiprocessing as mp

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/scripts')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE
from ch2_e529_dp_alns import evaluate_perm_dp, INST, OUT, FINE

sys.stdout.reconfigure(line_buffering=True)

BAK = OUT + ".bak.20260615.e618"
WAIT_MAX = 40          # max epoch-buckets to advance when stuck (40*q ≈ 2d)


def construct(cheap_min, exc_min, n, T, n_exc, start, rng, rcl):
    """Randomized-greedy (GRASP) tour on the table. cheap_min[i,j,t]/exc_min are
    integer arrival-bucket DELTAS (ceil(tof/q)) or -1 if no edge. Returns a full
    permutation (len n) or None if construction dead-ends."""
    cur = start
    tb = 0
    exc_used = 0
    perm = [start]
    unvis = set(range(n)) - {start}
    while unvis:
        # gather cheap candidates at current bucket, advancing on dead-end
        chosen = None
        for w in range(WAIT_MAX + 1):
            t = tb + w
            if t >= T:
                break
            cands = []   # (arr_bucket, j, is_exc)
            for j in unvis:
                d = cheap_min[cur, j, t]
                if d >= 0:
                    cands.append((t + d, j, False))
            if not cands and exc_used < n_exc:
                for j in unvis:
                    d = exc_min[cur, j, t]
                    if d >= 0:
                        cands.append((t + d, j, True))
            if cands:
                cands.sort(key=lambda c: c[0])
                pick = cands[rng.randrange(min(rcl, len(cands)))]
                chosen = (pick[0], pick[1], pick[2])
                break
        if chosen is None:
            return None
        arr, j, is_exc = chosen
        if arr >= T:
            return None
        perm.append(j)
        unvis.discard(j)
        if is_exc:
            exc_used += 1
        cur = j
        tb = arr
    return perm


def worker(args):
    wid, max_wall_s, rcl, bank_path = args
    kt = KTTSP(INST); n = kt.n
    rng = random.Random(wid * 104729 + 7)
    log = lambda m: print(f"[w{wid}] {m}", flush=True)

    d = np.load(FINE)
    cheap_tab = d['cheap']; exc_tab = d['exc']; t_starts = d['t_starts']
    q = float(t_starts[1] - t_starts[0]); T = len(t_starts)
    # precompute integer arrival-bucket deltas; -1 where no edge
    with np.errstate(invalid='ignore'):
        cheap_min = np.where(np.isfinite(cheap_tab),
                             np.ceil(cheap_tab / q), -1).astype(np.int32)
        exc_min = np.where(np.isfinite(exc_tab),
                           np.ceil(exc_tab / q), -1).astype(np.int32)
    log(f"table ready q={q} T={T} n_exc={kt.n_exc}")

    bank = json.load(open(bank_path))
    bank_mk = float(kt.fitness(bank[0]['decisionVector'])[0])
    best_mk = bank_mk
    log(f"bank mk={bank_mk:.4f}")

    t0 = time.time()
    n_built = 0; n_dead = 0; n_dpok = 0; n_dpfail = 0
    best_seen = math.inf
    while time.time() - t0 < max_wall_s:
        start = rng.randrange(n)
        perm = construct(cheap_min, exc_min, n, T, kt.n_exc, start, rng, rcl)
        if perm is None or len(perm) != n:
            n_dead += 1
            continue
        n_built += 1
        result = evaluate_perm_dp(kt, perm, cheap_tab, exc_tab, q, T)
        if result is None:
            n_dpfail += 1
            continue
        n_dpok += 1
        mk = result['mk']
        if mk < best_seen:
            best_seen = mk
        if mk < best_mk - 1e-4:
            x_full = list(result['times']) + list(result['tofs']) + \
                      [float(p) for p in perm]
            if not Path(BAK).exists():
                Path(BAK).write_bytes(Path(bank_path).read_bytes())
            tmp = bank_path + '.tmp'
            Path(tmp).write_text(json.dumps([{
                'decisionVector': x_full, 'problem': 'small',
                'challenge': CHALLENGE}]))
            chk = json.loads(Path(tmp).read_text())
            chk_mk = float(kt.fitness(chk[0]['decisionVector'])[0])
            if chk_mk < best_mk - 1e-4:
                os.replace(tmp, bank_path)
                best_mk = chk_mk
                log(f"BANKED {chk_mk:.4f}d (was {bank_mk:.4f}) start={start}")
            else:
                os.remove(tmp)
        if (n_built + n_dead) % 2000 == 0:
            el = time.time() - t0
            log(f"built={n_built} dead={n_dead} dpok={n_dpok} dpfail={n_dpfail} "
                f"best_seen={best_seen:.3f} ({el/60:.1f}min, "
                f"{(n_built+n_dead)/el:.0f} attempts/s)")
    log(f"done. built={n_built} dead={n_dead} best_seen={best_seen:.4f}")
    return wid, best_seen


def main(n_workers=4, wall_h=24, rcl=3):
    if not Path(FINE).exists():
        print(f"ERR table missing {FINE}"); return
    print(f"E-618 GRASP multi-start. workers={n_workers} wall_h={wall_h} rcl={rcl}",
          flush=True)
    if not Path(BAK).exists():
        Path(BAK).write_bytes(Path(OUT).read_bytes())
    args = [(i, wall_h * 3600, rcl, OUT) for i in range(n_workers)]
    with mp.Pool(n_workers) as pool:
        res = pool.map(worker, args)
    print("\nAll workers done.", flush=True)
    for wid, bs in res:
        print(f"  w{wid}: best_seen={bs:.4f}d", flush=True)


if __name__ == '__main__':
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    wh = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    rcl = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    main(n_workers=nw, wall_h=wh, rcl=rcl)
