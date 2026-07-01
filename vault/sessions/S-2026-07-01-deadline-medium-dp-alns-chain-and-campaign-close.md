# S-2026-07-01 — Deadline day: medium DP-ALNS chain + campaign close

Deadline Jul 1 14:00 CEST. All solutions submitted by the user before
the deadline; campaign concluded.

## Final submitted standing

- **Ch1 trajectory: 373,308.8 kg — RANK GAIN** (+7,712 over the original
  365,597; beats the rank threshold 372,729.017 by +580). The session's
  headline win, from refuting a false feasibility "wall": the idD=0
  hardcode bug + the solver "valid" flag (CMA penalty threshold) ≠
  official `udp.fitness<0`, plus the high arrival-v_inf transfers being
  stale basin-misses recoverable by the eccentric backward-shoot
  (UDPBackEcc, free TOF) at the real idD. See [[ch1-moderate-tof-idd0-bug]],
  [[ch1-trajectory-udp-floor-confirmed]], E-757/E-758.
- Ch2 large 879.528 d (rank 3); medium 182.11 d (rank 4); small 112.996;
  matching-i/ii held.

## Medium DP-ALNS chain — ran out of time (null)

Attempted the last live rank lever: medium 182.11 → rank-1 (172, −10d).
Built + ran the full precompute chain scoped to the medium tour span
(T_STARTS 0–220d):

- **E-531** coarse tcoupled table: 10.8h (32,580 pairs).
- **E-542** curated fine pair-set: 5.0h (4,682 pairs, 64.7% cheap cells).
- **E-545** DP-ALNS: launched ~12:33, single-chain DP over T=2200 ran
  >13s/iteration — did not clear even 200 iters before the deadline, no
  improvement over the 182.11 bank. Killed at wind-down.

**Lesson (confirms [[feedback-instrument-experiments]] economics):** the
precompute chain (≈16h) consumed almost the entire window, leaving the
actual DP-ALNS search starved (~1.5h, and each iter too heavy to matter).
For a deadline-bounded rank shot, the precompute-to-search time budget has
to be planned backward from the deadline — a 16h precompute for a same-day
rank attempt is self-defeating. The medium rank-1 gap (−10d) was always a
long shot; the chain never got to test it.

## Housekeeping

Backlog only (not this-session drift): 16 unpushed commits (no-push
policy), 30 dangling links + 110 cache-no-generator files (weekly-triage
backlog). Session-relevant vault/solution work committed; `.bak`/sandbag
files left untracked as intended.
