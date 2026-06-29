---
date: 2026-06-29
type: session
tags: [ch2, large, small, medium, 8h-window, verification, feasibility-bug, floors]
banks_end: {large: 879.53, medium: 182.11, small: 112.996, ch1: 364932}
---
# S-2026-06-29 — Ch2 8h autonomous window: floors verified, one feasibility-bug caught

User granted an 8h autonomous ch2 window ("explore ALL levers, NEVER GIVE UP"). Outcome: **ch2 is at
evidence-based method floors on all three instances**, with real but modest gains and one important
self-inflicted-bug lesson.

## Real gains
- **Ch2-large 932.53 → 879.53 d** (−53d over the window; rank-3 with growing cushion). The decisive bank was the
  **exact-clock worst-leg repair (E-748, −11.46d)** — the *correct* version of the perturb-then-retime E-747 that
  failed 0/45 (epoch-shift fragility, C-036). Earlier comp0 pass-2 + smalls reorder carried 932→890.
- **Medium upload corrected** to the held rank-1 best **182.11** (was stale 189.10; E-568/E-734). Now ready.

## Large rank-2 — exhausted, verdict E-752 (hard-shell-bound)
Drove the entire reorder/completion family: worst-leg repair (banked then plateaued), forward beam (walls
546/601), backward beam (walls 324; **33 cities bidirectionally hard**, E-750), completion-by-insertion (cheap
546-core is 255d/0-exc but grafting the 55 hard cities → **1338d ≫ 804**; the core is cheap only by omitting them,
E-751), SA order-search (0 accepts/25 iters, plateaued). **Root cause measured:** 29 comp0 cities have <10 cheap
neighbours (worst 6-8 vs median 152); the cheap graph is **faithful** (dense1d built with max_revs=20 + E-721
recompute, NOT under-counted). The hard-shell is structurally real → rank-2 (682) needs the hard cities cheaper
than the cheap graph allows = denser graph / different transfer model = competitor's research-grade edge. **879.53
rank-3 is our method floor.**

## Small — floor confirmed, and a FEASIBILITY-CHECK BUG caught (E-753)
A joint order+epoch SA appeared to smash 112.996 → 95.8 → **0.039d** (impossible). The tell triggered rigorous
verification: **my SA used `max(constraints) ≤ 1e-6` instead of `kt.is_feasible`** — which accepts *negative*
f[3] (chronologically INCONSISTENT schedules where you arrive after the next departure). The SA drove times[-1]→0
to exploit `makespan = times[-1]+tofs[-1]`. **The "breakthrough" was never a valid solution.** Fixed to
`kt.is_feasible` → the SA does NOT beat 112.996. Small is genuinely floored; the audit (ch2-small-floor-14292)
was right. **No bank was ever corrupted** (caught before any write/submit).

### Lesson (reinforces scientific-bug-surfacing-method)
The campaign's recurring optimistic/partial-evaluator bug reappeared **in my own check** — never hand-roll
constraint logic, always use the problem's `is_feasible`; and **rigorous skeptical verification (the 0.039 tell +
independent re-derivation) is what caught a false rank-1 before damage.** Every result now gets is_feasible +
exc≤5 + chronology + all-cities re-derivation before being believed.

## End state (all is_feasible=True, all held/unsubmitted)
large 879.53 (r3) · medium 182.11 (r1, upload aligned) · small 112.996 (r6) · ch1 364,932. The dominant remaining
action is the **user's submission decision** — search EV on ch2 is ~zero (evidence-based floors). E-745…E-753
committed + pushed.
