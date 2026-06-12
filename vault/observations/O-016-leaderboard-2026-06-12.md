---
id: O-016
type: observation
tags: [observation, leaderboard, all-instances]
date: 2026-06-12
status: live snapshot 11:10, per-user-best dedup, via scripts/fetch_leaderboards.py
related: [[O-002-leaderboard-2026-05-18]], [[E-037-ch2-medium-epoch-aware-cluster-decomp]], [[E-039-ch1-matching-evaluator-audit]]
---

# O-016 — Leaderboard snapshot 2026-06-12 11:10 (live GraphQL)

Fetched with the now-persisted `scripts/fetch_leaderboards.py` (P1 done).
NOTE: the API `rank` field is per-USER; cutoffs below are per-user-best
scores, dense-ranked. "Us" = current banks, NOT submitted (0 pts live).

| Instance | teams | our bank | rank if submitted | next cutoff (gap) |
|---|---|---|---|---|
| Trajectory | 6 | 236,420.5 | **r6** | r5 372,729 (+136k — unreachable) |
| Matching I | 10 | 33,338.184 | **r9** | r8 33,364.5 (+26.3); r5 33,427.2 (+89.0); r1 33,555.6 (+217.4) |
| Matching II | 10 | 72,200.728 | **r7** | r6 72,327.4 (+126.7); r5 72,373.1 (+172.4); r1 73,714.0 |
| Ch2 small | 8 | 116.3738 | **r6** | r5 111.7875 (−4.586); r1 101.65 |
| Ch2 medium | 7 | 195.7748 | **r2** | **r1 195.6816 (−0.0932!)**; r3 216.95 below us |
| Ch2 large | 6 | 1048.9786 | **r2** | r1 424.62 (far); r3 1238.5 below us |

Key deltas vs the 04:00 review assumptions:

- **Medium r1 = 195.6816 — only 0.093d above our bank.** Someone landed
  in (essentially) the same basin as our E-563 epoch-aware result. One
  timing-grid step (bank final-timed at 0.075d tof spacing / 0.1d
  t-quantum) → triggered E-040 ultrafine re-time.
- Matching I cutoffs moved up since 05-18 (r5 was 33,345, now 33,427);
  ladder is packed: +26 kg = r8, +89 kg = r5, +217 = r1 (×1/step).
- Matching II r6 unchanged at 72,327.4; today's LNS plateau 72,204.3
  confirms LNS won't cross — needs the exact-ILP push (E-039 verdict).
- Points if submitted now (matching-ii ×4/3 assumed, P4 unresolved):
  traj 8.89 + m-i 2.0 + m-ii 5.33 + small 5.0 + medium 12.0 + large
  16.0 ≈ **49.2 pts** (m-ii ×1 variant: 47.9). Currently 0.
