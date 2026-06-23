---
id: C-034
type: concept
status: validated
tags: [optimization, routing, beam-search, ch2, time-dependent, technique]
scope: optimization/time-dependent-routing
confidence: high
created: 2026-06-23
sources:
  - "Internal: E-710 M2/M3 (ch2_giant_fine_beam.py) — broke the 367/601 wall, 558/601 @ 283 d"
  - "Ow & Morton — Filtered beam search in scheduling"
related: ["[[C-010-constrained-hamiltonian-time-dependent-routing]]", "[[C-033-fast-faithful-oracle]]", "[[C-032-kttsp-problem]]", "[[C-013-cluster-bridge-insertion-pattern]]", "[[C-011-metaheuristic-local-search-routing]]", "[[M-general-basin-overarching-search]]"]
---

# C-034 — Time-aware beam construction for narrow-window TD-TSP

*The global constructor that dissolved a wall thought to be structural.
Build the tour order AND its timing together, carrying an exact running
clock per state, and keep a width-W frontier so promising-but-not-
greediest branches survive to reach cities the greedy strands.*

## The problem class

A time-dependent TSP / constrained Hamiltonian path (see
[[C-010-constrained-hamiltonian-time-dependent-routing]],
[[C-032-kttsp-problem]]) where each edge (i,j) is feasible/cheap only in
epoch-specific windows, the objective is makespan (last arrival), and a
small budget of exception (expensive) legs is allowed. The Ch2 "giant"
(601 cities) is the instance.

## Why greedy walls — and why it's NOT structural

A myopic earliest-arrival greedy dives into the locally densest region
and **strands at ~367/601**: by the epoch it reaches, the forward-
reachable frontier is exhausted — the remaining "hard-shell" cities
needed earlier departures whose windows have closed. For weeks this was
read as a *genuine* global wall (E-664→667, E-709) and large was priced
as a moonshot. **It was a greedy artifact.** A static-cost global solver
is even worse (strands at 10/601 — it ignores *when* windows open;
E-709 #3). The wall lives between "myopic" and "static," exactly where a
time-aware *beam* operates.

## The construction

Each beam **state** carries `(last_city, exact_clock t, visited_set,
path, exceptions_used)`. Per depth:

1. **Expand** every state via the fast-faithful oracle
   ([[C-033-fast-faithful-oracle]]): table-pruned candidate cities, each
   with an EXACT cheap arrival at the state's real clock. The clock makes
   it time-dependent; the oracle makes it accurate-and-fast.
2. **Exceptions on a near-stuck frontier only.** When cheap candidates
   run low (< 4) and budget remains, allow one expensive (dv ≤ dv_exc)
   leg — bounded neighbour scan. (Firing exceptions every step instead
   crippled throughput; fire them only where genuinely stuck.)
3. **Prune to width W** by earliest clock, with light diversity (dedup by
   last-city) so the frontier doesn't collapse onto one sub-region — the
   diversity is what preserves access to the stranded tail.

## Result (E-710, the giant)

| constructor | threads | makespan | d/leg |
|---|---|---|---|
| static-cost global TSP | 10/601 | — | — |
| earliest-arrival greedy | 367/601 | — | ~0.30→ |
| **fine-tof beam W=60** | **558/601** | **283 d** (of 558) | 0.29–0.51 |
| rank-1 competitor | 601/601 | 424.62 d | 0.404 |

The beam threaded **0.41–0.51 d/leg through depth 500 — at/under rank-1's
average** — proving a *complete* tour on this trajectory lands well under
424 d (rank-1 territory). Remaining work: close the last ~43 hard-shell
cities (wider W, exceptions, or window-epoch clustering / tail-repair).

## Design rules (transferable)

- **Carry the exact clock in the state** — the entire point. A state's
  candidate set depends on its arrival time; sharing a global clock or
  using static costs reintroduces the failure.
- **Width buys tail access, not just better cost.** Here W>1 is the
  difference between stranding (367) and (near-)completion (558+). Treat
  W as the lever against frontier exhaustion ([[M-general-basin-overarching-search]]).
- **Diversity in the prune, or the frontier collapses.** Near the end the
  beam shrinks toward one visited-set; dedup/diversify to keep variety.
- **Spend exceptions only where stuck.** Cheap legs dominate; exceptions
  are a scarce tail resource, not a per-step option.

## Relation to cluster+LKH

This is a *lighter* member of the time-aware decomposition family the
competitor (TGMA) is inferred to use (cluster by window-compatibility →
LKH within; [[C-013-cluster-bridge-insertion-pattern]]). If the beam
completes under 424 d, the heavier cluster+LKH build is unnecessary; if
it walls short, explicit window-epoch clustering is the next refinement.

## In practice

- `scripts/ch2_giant_fine_beam.py W K` — the constructor.
- Checkpoints best path to `cache/ch2_giant_fine_beam_best.json`
  (reboot-surviving, resumable).
