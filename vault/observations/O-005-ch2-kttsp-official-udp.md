---
id: O-005
type: observation
status: confirmed
tags: [ch2, optimization, lambert, baseline]
source: "reference/spoc4_udp/kttsp-{small,medium,large}.py (official udpFile, fetched 2026-05-19, L-002) + easy/medium/hard.kttsp"
created: 2026-05-19
referenced_by: ["[[H-003-ch2-small-lambert-metaheuristic]]"]
supersedes:
superseded_by:
---

# O-005 — Ch2 KTTSP official UDP + instances

## Observation

**Problem** (official `KTTSP`, 275-line UDP — authoritative scorer):
time-dependent orbital ATSP. N tomatoes on fixed Keplerian orbits
about the Moon (`pk.planet.keplerian`, MU_MOON=4.9048695e12).

- **Instances** (starter `.kttsp` = GraphQL id): easy=`small`
  N=49 (dim 145), medium=`medium` N=181 (541), hard=`large`
  N=1051 (3151). `small` header: `p kttsp 0.0 0.001 200.0 100.0
  600.0 5` → t0=0, min_tof=0.001 d, **max_time=200 d**,
  dv_threshold=100 m/s, dv_exception=600 m/s, n_exception=5.
- **Chromosome** x, len 3N−2: `times[0:N-1]` (departure, days),
  `tofs[N-1:2N-2]` (TOF, days), `order[2N-2:]` (N ints, perm 0..N-1).
- **fitness(x)** → `[total_time, perm_c, dv_c, time_c, dv_exc_c]`:
  - **objective `total_time = times[-1]+tofs[-1]`** (minimise; the
    leaderboard score; rank-3 `small` ≤ 111.76 d, O-002).
  - `perm_c = len(set(order))−N` → must be 0 (visit each once).
  - per leg i: `dv = compute_transfer(order[i],order[i+1],times[i],
    tofs[i])`; `dv_c = (#legs dv≤600) − (N−1)` → 0 ⇒ **every leg
    ≤ 600**; `dv_exc_c = (#legs 100<dv≤600) − 5` → ≤ 0 ⇒ **≤5
    legs in (100,600], rest ≤100**; `time_c` → 0 ⇒ **chronological
    `times[i]+tofs[i] ≤ times[i+1]`** for all i.
  - pygmo: nec=3 (perm,dv,time =0), nic=1 (dv_exc ≤0).
- **compute_transfer**: `pk.lambert_problem(r_i, r_j, tof_sec,
  MU_MOON, cw∈{F,T}, max_revs=20)`; best Δv = min over all
  branches/revs of `|v1−v_i| + |v2−v_j|`. Tomato eph via
  `keplerian.eph(t_days)`.

## Why it matters

H-003 target. Structure = ATSP with time-dependent Lambert edge
costs + a feasibility regime (≤100 m/s normal, ≤5 exception legs
≤600, chronology, makespan). Realistic approach (O-002: OR teams
strong here): precompute a feasible transfer/time structure, then
sequence+timing metaheuristic. Reuse combinatorial machinery
experience from Ch1 matching. Concept:
[[concepts/C-006-lambert-problem-and-orbital-tsp]].
Submission JSON: same `decisionVector`/`problem`/`challenge` shape,
`problem` ∈ {small,medium,large}.
