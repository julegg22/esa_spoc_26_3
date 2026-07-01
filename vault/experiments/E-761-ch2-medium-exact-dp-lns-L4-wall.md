---
id: E-761
type: experiment
status: analyzed — no improvement over bank 182.11; ladder sweep ⇒ wall_level L4
date: 2026-07-02
level: L6                      # same RE-RUN as small (exact-DP+LNS solver swap)
wall_level: L4                # encoding; L7 ruled out by 3-config convergence
assumes: [EVAL-lambert, MODEL-official-feas]
reruns: [ENC-grid, SOLVER-gtsp-exc]
code: scripts/ch2_medium_order_search.py
commit: e9ebdc3               # from the [PROV] line in the medium run logs
related: ["[[E-760-ch2-small-exact-dp-lns-validated]]", "[[E-734-ch2-medium-rank1-reclaimed-182]]", "[[assumptions]]", "[[M-general-abstraction-ladder-audit]]"]
---
# E-761 — Ch2-medium: exact-DP+LNS finds no improvement; the wall is L4 (encoding)

**Result.** The same exact-DP+LNS engine that beat the small bank produced **zero
improvement** on medium: proxy-best stayed at **182.11 = the bank** across three
configs — main or-opt (961k iters), 2-opt/seed7 (300k), or-opt/seed999 (300k).
The proxy is **exact** here (pos-control reproduces 182.11 exactly, no handicap),
so the search faithfully cannot beat the bank order.

**Ladder sweep (R1).** Three independent search configurations converging to the
identical value **rules out L7** (operators/basin). Given the proxy is exact and
the bank order (from E-734's DP order-search) is already a strong local opt, the
residual gap to rank-1 (172, −10 d) is at **L4 (encoding)** — the
cheap-restricted / uniform-grid / 8 d-tof representation cannot represent a
sub-182.11 tour. `wall_level: L4`.

**Contrast with small (E-760).** Small *improved* 1 d (112.996→111.96) then
plateaued (L4 for the rank-1 residual); medium **can't improve at all**. Both hit
the same encoding rung — medium harder because its bank already sits at the
representation floor. So `ENC-grid` (L4) now demonstrably walls **small AND
medium**; medium rank-1 needs the same L4 rebuild (finer TOFMAX/TQ + wider edge
set), a shared sub-problem.

**Bank impact.** None (medium bank stays 182.11, rank 4). Not submitted.

**Next (L1-signposted fork).** Recommend **graduating the validated method to
LARGE** (cluster-decompose+couple; biggest gap 879→424; the HRI hint is strongest
there) over grinding the shared small/medium L4 rebuild now. → E-762.
