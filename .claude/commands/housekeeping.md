---
description: Run the full housekeeping cadence in one pass — mechanical drift check, judgment review, invalidation-cascade checklist, doc-sync, and vault commit (optionally push)
argument-hint: "[push]  (append 'push' to git-push after the pass comes clean)"
---

You are running the project's **housekeeping cadence** in one pass. This bundles
every recurring hygiene action (CLAUDE.md §7 + META.md §15 + `doc_methodology.md`
§7). Fires at **resume, wind-down, and every `/loop` tick**. Do the steps in
order; fix what you can; end with the vault committed and a short report.

## 1. Mechanical drift (automated)
Run `python scripts/housekeeping_check.py` (use the project env python). It flags:
uncommitted vault, untracked scripts, unpushed commits, dangling `[[links]]`,
MEMORY.md pointer rot, cache-without-generator, and **un-triaged assumptions**
(refuted register rows whose `assumes:` dependents lack an `invalidation:`
overlay). **Fix each flagged item now** — don't batch it:
- dangling links → repoint or de-link;
- untracked scripts / uncommitted vault → stage by name + commit;
- cache-without-generator → commit the generator or note it;
- un-triaged assumptions → run the §15 **T6** cascade (step 3).
- **reproducibility gap** → any new/uncommitted `E-` node without a `commit:`
  SHA, or a banked result whose run log shows `[PROV] … +DIRTY`, is not
  replayable. Fill `commit:` from the run log's `[PROV]` line; if the producing
  run was `+DIRTY`, re-run on a clean tree before trusting/banking it.

## 2. Judgment review (M-001)
Ask, and act:
- Did this session produce a **reusable insight** not yet in a `T-`/`L-`/`C-`/`M-`
  node (or `doc_methodology.md` / `doc_lessons.md`)? If yes, write it.
- Is the **session note** (`vault/sessions/S-YYYY-MM-DD-*.md`) written/updated for
  what was decided and done?
- Are `MEMORY.md` pointers current for any new memory?

## 3. Invalidation-cascade checklist (META §15 triggers T1–T6)
For each that occurred this session, run the cascade (overlay `invalidation:{level}`,
triage RE-RUN / REFRAME / STILL-HOLDS):
- new `M-` with severity critical (T1); blocker `L-` on foundational code (T2);
- retrospective addendum to a closed H (T3); a corroboration reversal (T4);
- a wrong-track pattern-finding (T5);
- **an Assumption-Register row flipped** to suspect/refuted at any ladder level
  (T6) → `git grep "assumes:.*<ID>"`, overlay, triage.
Also the M-018 step-back triggers (3+ refutations on a branch, effort ≫ estimate).

## 4. Doc-sync
If the ladder, rules R1–R5, the register schema, the cascade, or the cadence
changed this session, update **`doc_methodology.md`** (and add a `doc_lessons.md`
case if a wall broke or a process root-cause surfaced) — in this same pass.

## 5. Commit
Stage the touched vault/doc/script files **by name** (no `git add -A`), commit
with a 1–2 sentence why-focused message (no AI-attribution trailer). Then
**`git status vault/` must end empty.**

## 6. Push (only if `$ARGUMENTS` contains `push`)
Push **rides on housekeeping** — housekeeping *is* the pre-push gate (clean tree,
no drift, docs synced). Only after steps 1–5 come clean: show the unpushed commits
(`git log --oneline @{u}..HEAD`), confirm the branch, then `git push`. If any
housekeeping item is still open, do **not** push — report what's blocking.
(Pushing is outward-facing; without the gate, drift escapes to the remote.)

## Report
End with: mechanical findings fixed, judgment/cascade items handled (or "none"),
docs synced (y/n), commit SHA, and push status. Keep it to a few lines.
