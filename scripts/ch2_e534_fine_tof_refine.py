"""E-534 — Ch2 small: fine-tof refinement on current bank schedule.

The audit (2026-05-30) D4 hostile-default flagged that our tof grid
floor is 0.025 d while spec dt_min is 0.001 d (25× coarser). The E-527
DP and E-529 ALNS used a 0.05 d tof grid step. This experiment
refines bank's schedule at tof step **0.0001 d** (500× finer than
the production grid), one leg at a time, with cascading chronology
updates.

Method per leg k (random order, multiple passes):
  Given current (t_k, tof_k), kind_k ∈ {cheap, exc}:
    1. Sweep tof' from 0.001 d to current tof_k + 1.0 d in 0.0001 d
       steps, computing Lambert dv at fixed departure t_k.
    2. Find smallest tof' with dv ≤ cap (cap=100 for cheap, 600 for exc).
    3. If tof' < tof_k by > 1 mD: replace, cascade chronology forward
       (subsequent legs' depart times shift earlier if slack allows).
    4. Verify downstream legs still feasible at new earlier t's.
  Iterate over all legs until no leg improves.

Cheap by design (1 core, ~minutes for one pass over 48 legs).
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
BAK = OUT + ".bak.20260607.e534"
RESULT = '/tmp/ch2_e534_result.json'

DV_CHEAP = 100.0
DV_EXC = 600.0

# Spec-floor tof: 0.001 d. Use 0.0001 d step for safety margin
TOF_GRID_STEP = 0.0001
TOF_MIN_SPEC = 0.001
TOF_MAX = 8.0
MAX_T = 200.0


def leg_dv(kt, i, j, t, tof):
    try:
        return float(kt.compute_transfer(i, j, t, tof))
    except Exception:
        return 1e9


def classify_leg(dv):
    if dv <= DV_CHEAP + 1e-6:
        return 'cheap', DV_CHEAP
    elif dv <= DV_EXC + 1e-6:
        return 'exc', DV_EXC
    else:
        return None, None


def fine_tof_search(kt, i, j, t, cap, tof_max_search):
    """Find smallest tof in [TOF_MIN_SPEC, tof_max_search] s.t. dv ≤ cap."""
    n_steps = int(round((tof_max_search - TOF_MIN_SPEC) / TOF_GRID_STEP)) + 1
    n_steps = min(n_steps, 30000)  # cap at 30k Lambert calls per leg (~9s)
    tofs = np.linspace(TOF_MIN_SPEC, tof_max_search, n_steps)
    for tof in tofs:
        dv = leg_dv(kt, i, j, t, float(tof))
        if dv <= cap + 1e-6:
            return float(tof), float(dv)
    return None, None


def main(max_passes=3):
    kt = KTTSP(INST); n = kt.n
    bank = json.load(open(OUT))
    dv = bank[0]['decisionVector']
    times = list(dv[:n-1]); tofs = list(dv[n-1:2*(n-1)])
    perm = [int(x) for x in dv[2*(n-1):]]
    bank_mk_entry = float(kt.fitness(dv)[0])
    print(f"E-534 fine-tof refinement. Bank entry: {bank_mk_entry:.6f}d",
          flush=True)

    # Classify legs
    kinds = []
    caps = []
    for k in range(n - 1):
        d = leg_dv(kt, perm[k], perm[k+1], times[k], tofs[k])
        kind, cap = classify_leg(d)
        kinds.append(kind); caps.append(cap)
        if kind is None:
            print(f"  WARN leg {k} has unclassifiable dv={d:.2f}", flush=True)
    n_cheap = kinds.count('cheap'); n_exc = kinds.count('exc')
    print(f"  Legs: {n - 1} ({n_cheap} cheap, {n_exc} exc)", flush=True)

    rng = random.Random(0)
    total_shaved = 0.0
    pass_count = 0

    for pass_i in range(max_passes):
        pass_count += 1
        order = list(range(n - 1)); rng.shuffle(order)
        pass_imp = 0.0
        n_improved = 0
        t_pass = time.time()

        for k in order:
            i, j = perm[k], perm[k+1]
            cap = caps[k]
            cur_tof = tofs[k]
            dep_t = times[k]

            # Fine search for smaller tof at the same departure
            new_tof, new_dv = fine_tof_search(
                kt, i, j, dep_t, cap, cur_tof - 1e-6)
            if new_tof is None: continue
            if cur_tof - new_tof < 1e-4: continue  # too small to bother

            # Tentative: apply this tof and cascade
            tent_tofs = list(tofs)
            tent_tofs[k] = new_tof
            tent_times = list(times)
            # Cascade: subsequent legs can shift earlier
            for k2 in range(k + 1, n - 1):
                earliest = tent_times[k2-1] + tent_tofs[k2-1]
                if tent_times[k2] > earliest:
                    tent_times[k2] = earliest
            # Verify downstream legs still feasible at new t's
            ok = True
            for k2 in range(k + 1, n - 1):
                dv2 = leg_dv(kt, perm[k2], perm[k2+1],
                              tent_times[k2], tent_tofs[k2])
                if dv2 > caps[k2] + 1e-6:
                    ok = False
                    break
            if not ok:
                continue

            mk_old = times[-1] + tofs[-1]
            mk_new = tent_times[-1] + tent_tofs[-1]
            delta = mk_old - mk_new
            if delta < 1e-4: continue

            # Accept
            tofs = tent_tofs; times = tent_times
            n_improved += 1
            pass_imp += delta
            total_shaved += delta
            mk_cur = times[-1] + tofs[-1]
            print(f"  pass {pass_i} leg {k}: tof {cur_tof:.4f}→{new_tof:.4f} "
                  f"(Δ={cur_tof-new_tof:.4f}d) shaved {delta:.4f}d, "
                  f"mk={mk_cur:.6f}d", flush=True)

        wall_pass = time.time() - t_pass
        mk_pass = times[-1] + tofs[-1]
        print(f"  -- pass {pass_i}: {n_improved} improvements, "
              f"shaved {pass_imp:.4f}d, mk={mk_pass:.6f}d, "
              f"wall {wall_pass:.0f}s", flush=True)
        if pass_imp < 1e-4:
            print(f"  no more improvements; stopping.", flush=True)
            break

    # Validate
    x_final = times + tofs + [float(p) for p in perm]
    fit_final = kt.fitness(x_final)
    feas_final = bool(kt.is_feasible(fit_final))
    mk_final = float(fit_final[0])
    print(f"\nFinal: mk={mk_final:.6f}d feasible={feas_final} "
          f"viols={fit_final[1:]}", flush=True)
    print(f"Total shaved from bank: {bank_mk_entry - mk_final:.6f}d",
          flush=True)

    banked = False
    if feas_final and mk_final < bank_mk_entry - 1e-4:
        if Path(OUT).exists() and not Path(BAK).exists():
            Path(BAK).write_bytes(Path(OUT).read_bytes())
        tmp = OUT + '.tmp'
        Path(tmp).write_text(json.dumps([{
            'decisionVector': x_final, 'problem': 'small',
            'challenge': CHALLENGE,
        }]))
        os.replace(tmp, OUT)
        banked = True
        print(f"\n>>> BANKED: {mk_final:.6f}d "
              f"({bank_mk_entry - mk_final:.6f}d under prev)",
              flush=True)

    Path(RESULT).write_text(json.dumps({
        'bank_entry': bank_mk_entry, 'mk_final': mk_final,
        'shaved_d': bank_mk_entry - mk_final,
        'feasible': feas_final, 'banked': banked,
        'passes': pass_count, 'tof_step_d': TOF_GRID_STEP,
    }))


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    main(max_passes=n)
