"""E-044 v2 — Ch2 LARGE: DEFRAGMENTING global ring sweep.

E-580 v1 (within-run sweep) gained only 7.6d because it kept the bank's
ring fragmentation: the 3 big-shell rings are each visited in 2-4
separate fragments, and every re-entry is a phase-miss. v2 rebuilds the
visiting order to finish each ring in ONE contiguous phase sweep.

Construction (chronological, self-consistent epochs):
  - Order: small shell first (3 clean rings, period 0.238d), then big
    shell rings (period 1.906d). Within a shell, greedily pick the next
    ring by cheapest bridge from the current node.
  - Within a ring: sweep all members in phase (argument-of-latitude)
    order, direction chosen to minimise the entry catch-up.
  - Each leg: earliest feasible cheap transfer (+bounded wait); spend an
    exception only on a ring->ring bridge when no cheap bridge exists,
    budget kt.n_exc total.
Compares realised makespan to the 1041.33 incumbent; candidate -> /tmp
ONLY (guard-banked separately). Never touches solutions/upload/.
"""
import json
import os
import sys
import time

import numpy as np

ROOT = "/home/julian/Projects/esa_spoc_26_3"
sys.path.insert(0, f"{ROOT}/src")
from esa_spoc_26.ch2_kttsp import KTTSP, CHALLENGE  # noqa: E402
from esa_spoc_26.ch2_findtransfer_greedy import find_earliest_transfer  # noqa: E402

INST = (f"{ROOT}/reference/SpOC4/Challenge 2 Keplerian Tomato Traveling "
        "Salesperson Problem/problems/hard.kttsp")
BANK = f"{ROOT}/solutions/upload/large.json"
OUT = os.environ.get("E581_OUT", "/tmp/ch2_large_defrag_cand.json")

TOF_WINDOW = float(os.environ.get("E581_TOFWIN", "12.0"))
N_STEPS = int(os.environ.get("E581_NSTEPS", "120"))
WAIT_STEPS = int(os.environ.get("E581_WAITSTEPS", "16"))
WAIT_DT = float(os.environ.get("E581_WAITDT", "0.25"))
WAIT_BRIDGE = int(os.environ.get("E581_WAITB", "120"))
CURRENT_BANK = 1041.3340


def ring_labels(kt):
    a = kt.opar[:, 0] / 1000.0
    inc = np.degrees(kt.opar[:, 2]) % 360.0
    shell = np.where(a < 8000, 0, 1)
    plane = (np.round(inc / 15.0).astype(int) * 15) % 360
    return shell, plane


def phase_u(kt):
    return (kt.opar[:, 4] + kt.opar[:, 5]) % (2 * np.pi)


def leg(kt, i, j, t, allow_exc, wait_steps):
    tof, dv = find_earliest_transfer(kt, i, j, t, kt.dv_thr, TOF_WINDOW, N_STEPS)
    if tof is not None:
        return t, tof, False
    for w in range(1, wait_steps + 1):
        t_try = t + w * WAIT_DT
        if t_try >= kt.max_time - kt.min_tof:
            break
        tof, dv = find_earliest_transfer(kt, i, j, t_try, kt.dv_thr,
                                         TOF_WINDOW, N_STEPS)
        if tof is not None:
            return t_try, tof, False
    if allow_exc:
        for w in range(0, wait_steps + 1):
            t_try = t + w * WAIT_DT
            if t_try >= kt.max_time - kt.min_tof:
                break
            tof, dv = find_earliest_transfer(kt, i, j, t_try, kt.dv_exc,
                                             TOF_WINDOW, N_STEPS)
            if tof is not None:
                return t_try, tof, True
    return None


def sweep_ring(kt, members, entry, u):
    """Phase-ordered sweep of `members` starting adjacent to `entry`'s
    phase; pick the direction (fwd/bwd) whose first hop is the nearest
    forward catch-up. Returns the ordered node list (excludes entry)."""
    if not members:
        return []
    u0 = u[entry]
    du = [( (u[j] - u0) % (2 * np.pi), j) for j in members]
    fwd = [j for _, j in sorted(du)]                       # increasing phase
    bwd = [j for _, j in sorted(du, key=lambda p: -p[0])]  # decreasing
    # forward catch-up of first node (smallest positive du) is cheap;
    # default forward. Heuristic: choose the order whose first node has
    # the smallest |du| so the entry leg is short.
    return fwd if du and min(d for d, _ in du) <= (2 * np.pi - max(d for d, _ in du)) else bwd


def main():
    kt = KTTSP(INST)
    n = kt.n
    bank = json.load(open(BANK))[0]["decisionVector"]
    perm0 = [int(round(v)) for v in bank[2 * (n - 1):]]
    print(f"[E-581] incumbent mk={CURRENT_BANK} start node={perm0[0]}",
          flush=True)

    shell, plane = ring_labels(kt)
    u = phase_u(kt)
    rings = {}
    for i in range(n):
        rings.setdefault((int(shell[i]), int(plane[i])), []).append(i)

    start = perm0[0]
    # ring visiting order: start's ring first, then remaining rings of the
    # same shell, then the other shell. Within a tier, nearest-by greedy is
    # resolved at walk time via cheapest bridge; here fix a static order:
    # same shell (ascending plane), then other shell (ascending plane).
    s0 = int(shell[start])
    same = sorted([r for r in rings if r[0] == s0])
    other = sorted([r for r in rings if r[0] != s0])
    # rotate `same` so start's ring is first
    start_ring = (s0, int(plane[start]))
    si = same.index(start_ring)
    same = same[si:] + same[:si]
    ring_order = same + other
    print(f"[E-581] ring order: {ring_order}", flush=True)

    t0 = time.time()
    out_perm = [start]
    times, tofs = [], []
    exc_used = 0
    t = 0.0
    cur = start
    for idx, r in enumerate(ring_order):
        members = [m for m in rings[r] if m != cur]
        if not members and r == start_ring:
            continue
        seq = sweep_ring(kt, members, cur, u)
        # try both directions, keep the one with smaller end time
        seq_rev = list(reversed(seq))
        best = None
        for order in ([seq, seq_rev] if seq else [[]]):
            tt, tf = [], []
            cc, tcur, exc2 = cur, t, exc_used
            ok = True
            for li, j in enumerate(order):
                allow_exc = (li == 0 and exc2 < kt.n_exc)
                ws = WAIT_BRIDGE if li == 0 else WAIT_STEPS
                res = leg(kt, cc, j, tcur, allow_exc, ws)
                if res is None:
                    ok = False
                    break
                td, tof, ie = res
                tt.append(td)
                tf.append(tof)
                tcur = td + tof
                if ie:
                    exc2 += 1
                cc = j
            if ok and (best is None or tcur < best[0]):
                best = (tcur, tt, tf, exc2, list(order))
        if best is None:
            print(f"[E-581] ring {r} ({len(members)} nodes) UNWALKABLE "
                  f"at t={t:.1f} exc={exc_used} — abort", flush=True)
            return
        tcur, tt, tf, exc2, order = best
        out_perm.extend(order)
        times.extend(tt)
        tofs.extend(tf)
        t, exc_used, cur = tcur, exc2, (out_perm[-1])
        print(f"[E-581] ring {idx+1}/{len(ring_order)} {r} "
              f"+{len(order)} -> t={t:.2f}d exc={exc_used} "
              f"({time.time()-t0:.0f}s)", flush=True)

    assert len(out_perm) == n and len(set(out_perm)) == n, "not a perm"
    mk = times[-1] + tofs[-1]
    x = list(map(float, times)) + list(map(float, tofs)) + \
        [float(v) for v in out_perm]
    fit = kt.fitness(x)
    feas = kt.is_feasible(fit)
    print(f"\n[E-581] RESULT walk mk={mk:.4f}d exc={exc_used} "
          f"official mk={fit[0]:.4f} feas={feas} viol={fit[1:]} "
          f"(incumbent {CURRENT_BANK})", flush=True)
    if feas and fit[0] < CURRENT_BANK - 1e-6:
        json.dump([{"decisionVector": x, "problem": "large",
                    "challenge": CHALLENGE}], open(OUT, "w"))
        print(f"[E-581] CANDIDATE WRITTEN {OUT} mk={fit[0]:.4f}", flush=True)
    else:
        print("[E-581] no improvement over incumbent — nothing written",
              flush=True)


if __name__ == "__main__":
    main()
