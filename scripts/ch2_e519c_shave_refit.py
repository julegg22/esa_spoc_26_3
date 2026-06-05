"""E-519c — Ch2 small: shave-and-refit-downstream on bank perm.

E-519b found leg-only refinement converges fast (just 1 leg shaved
0.055 d). The limit: shaving leg k almost always breaks downstream
(leg k+1 at new earlier t needs different tof). E-519c fixes this by
RE-OPTIMIZING all downstream legs after a shave.

Method per pass:
  For each leg k (random order):
    Sweep (t_k, tof_k) over a fine grid; for each candidate (t', tof'):
      - tentative new t_k', tof_k'
      - downstream re-fit: for legs k+1..n-2, find minimum-tof feasible
        transfer at the new cascaded t (respecting kind = cheap/exc per
        current bank). If any downstream leg has no feasible transfer,
        reject this candidate.
      - if cascaded makespan < current_best: accept
    Take the best candidate (if any).
  Iterate passes until no leg improves.

Faster Lambert: precompute a small per-leg grid lookup.
"""
from __future__ import annotations
import sys, os, json, time, random
from pathlib import Path
import numpy as np

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE

sys.stdout.reconfigure(line_buffering=True)

INST = ("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/"
        "Challenge 2 Keplerian Tomato Traveling Salesperson Problem/"
        "problems/easy.kttsp")
OUT = "/home/julian/Projects/esa_spoc_26_3/solutions/upload/small.json"
BAK = OUT + ".bak.20260602.e519c"
RESULT = '/tmp/ch2_e519c_result.json'

BANK_THRESHOLD = 142.8359  # current bank from E-519b
DV_CHEAP = 100.0
DV_EXC = 600.0
TOF_MIN = 0.001
TOF_MAX = 8.0


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return float('inf')


def find_min_tof_at(kt, i, j, t, dv_cap, tof_lo=TOF_MIN, tof_hi=TOF_MAX,
                    n=200):
    """Find the smallest tof at departure t such that dv ≤ dv_cap.
    Returns (tof, dv) or (None, None)."""
    grid = np.linspace(tof_lo, tof_hi, n)
    best_tof = None
    best_dv = None
    for tof in grid:
        dv = leg_dv(kt, i, j, float(t), float(tof))
        if dv <= dv_cap + 1e-6:
            best_tof = float(tof); best_dv = float(dv)
            break  # earliest = smallest tof passing threshold
    return best_tof, best_dv


def classify_legs(kt, perm, times, tofs):
    kinds = []
    for k in range(len(perm) - 1):
        dv = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
        kinds.append('exc' if dv > DV_CHEAP + 1e-6 else 'cheap')
    return kinds


def refit_downstream(kt, perm, times, tofs, kinds, k_start):
    """Re-optimize legs k_start..n-2 sequentially: at each leg, take
    the smallest tof feasible (cheap if kind='cheap', exc if 'exc').
    If any leg has no feasible transfer, return None.
    Returns (new_times, new_tofs) or None.
    """
    n_legs = len(perm) - 1
    new_t = list(times); new_tof = list(tofs)
    for k in range(k_start, n_legs):
        earliest = new_t[k-1] + new_tof[k-1] if k > 0 else 0.0
        if new_t[k] < earliest:
            new_t[k] = earliest
        kind = kinds[k]
        cap = DV_EXC if kind == 'exc' else DV_CHEAP
        i, j = perm[k], perm[k+1]
        tof, dv = find_min_tof_at(kt, i, j, new_t[k], cap, n=200)
        if tof is None:
            return None
        new_tof[k] = tof
    return new_t, new_tof


def schedule_mk(times, tofs):
    return times[-1] + tofs[-1]


def try_leg_shave_then_refit(kt, perm, times, tofs, kinds, k,
                              n_t=40, n_tof=80):
    """Sweep (t_k, tof_k), refit downstream, accept best."""
    earliest_t = (times[k-1] + tofs[k-1]) if k > 0 else 0.0
    cur_dep = times[k]; cur_tof = tofs[k]
    kind = kinds[k]
    cap = DV_EXC if kind == 'exc' else DV_CHEAP
    i, j = perm[k], perm[k+1]

    dep_lo = max(earliest_t, 0.0)
    dep_hi = cur_dep + 2.0
    dep_grid = np.linspace(dep_lo, dep_hi, n_t)
    tof_lo = max(TOF_MIN, min(cur_tof * 0.25, cur_tof - 2.5))
    tof_hi = min(TOF_MAX, max(cur_tof * 2.0, cur_tof + 2.5))
    tof_grid = np.linspace(tof_lo, tof_hi, n_tof)

    cur_mk = schedule_mk(times, tofs)
    best_mk = cur_mk - 1e-6
    best_state = None

    for t in dep_grid:
        for tof in tof_grid:
            dv = leg_dv(kt, i, j, float(t), float(tof))
            if dv > cap + 1e-6:
                continue
            # tentative: apply this leg, then refit downstream
            tent_t = list(times); tent_tof = list(tofs)
            tent_t[k] = float(t); tent_tof[k] = float(tof)
            # cascade earliest
            for k2 in range(k+1, len(tent_t)):
                e2 = tent_t[k2-1] + tent_tof[k2-1]
                if tent_t[k2] < e2:
                    tent_t[k2] = e2
            r = refit_downstream(kt, perm, tent_t, tent_tof, kinds, k+1)
            if r is None:
                continue
            new_t, new_tof = r
            mk_n = schedule_mk(new_t, new_tof)
            if mk_n < best_mk:
                best_mk = mk_n
                best_state = (new_t, new_tof, float(t), float(tof), cur_mk - mk_n)
    return best_state


def main(max_passes=5):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    times = list(dv[:n-1]); tofs = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]

    x0 = times + tofs + [float(p) for p in perm]
    fit0 = kt.fitness(x0)
    feas0 = bool(kt.is_feasible(fit0))
    mk0 = schedule_mk(times, tofs)
    print(f"E-519c shave-and-refit on bank perm. "
          f"start={perm[0]} end={perm[-1]}", flush=True)
    print(f"Bank: mk={mk0:.4f}d  fit={fit0}  feas={feas0}", flush=True)

    kinds = classify_legs(kt, perm, times, tofs)
    n_exc = kinds.count('exc')
    print(f"Legs: {len(perm)-1}; cheap={kinds.count('cheap')} exc={n_exc}",
           flush=True)

    rng = random.Random(0)
    for pass_i in range(max_passes):
        order = list(range(n-1)); rng.shuffle(order)
        pass_imp = 0.0
        n_improved = 0
        t_pass = time.time()
        for k in order:
            t_leg = time.time()
            best = try_leg_shave_then_refit(kt, perm, times, tofs, kinds, k)
            wall_leg = time.time() - t_leg
            if best is not None:
                new_t, new_tof, new_dep, new_tof_k, delta = best
                times = new_t; tofs = new_tof
                pass_imp += delta; n_improved += 1
                mk_cur = schedule_mk(times, tofs)
                # re-classify legs (downstream tofs changed; kind may flip
                # if dv now in different regime). Keep kinds stable: only
                # accept if leg dv stays in original kind. We already
                # enforce per-leg cap above.
                print(f"  pass {pass_i} leg {k}: t={new_dep:.4f} "
                      f"tof={new_tof_k:.4f} → shaved {delta:.4f}d "
                      f"mk={mk_cur:.4f}d (leg wall {wall_leg:.1f}s)",
                       flush=True)
        wall_pass = time.time() - t_pass
        mk_pass = schedule_mk(times, tofs)
        print(f"  -- pass {pass_i}: {n_improved} improvements, total "
              f"shaved {pass_imp:.4f}d, mk={mk_pass:.4f}d, "
              f"wall {wall_pass:.0f}s", flush=True)
        if pass_imp < 1e-4:
            print("  no more improvements; stopping.", flush=True)
            break

    x_final = times + tofs + [float(p) for p in perm]
    fit_final = kt.fitness(x_final)
    feas_final = bool(kt.is_feasible(fit_final))
    mk_final = schedule_mk(times, tofs)
    print(f"\nFinal: mk={mk_final:.4f}d  fit={fit_final}  feas={feas_final}",
          flush=True)
    print(f"Total shaved from bank: {mk0 - mk_final:.4f}d", flush=True)

    banked = False
    if feas_final and mk_final < BANK_THRESHOLD - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {mk_final:.4f}d "
              f"({mk0 - mk_final:.4f}d under entry)", flush=True)

    Path(RESULT).write_text(json.dumps({
        'mk_entry': float(mk0), 'mk_final': float(mk_final),
        'shaved_d': float(mk0 - mk_final),
        'udp_feasible': feas_final, 'banked': banked,
    }))


if __name__ == '__main__':
    main()
