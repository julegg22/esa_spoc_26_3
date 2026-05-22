---
id: L-010
type: lesson
status: confirmed
tags: [optimization, scipy, slsqp, trust-constr, ip, gotcha]
kind: gotcha
scope: optimization/nlp + scipy
severity: warning
confidence: high
created: 2026-05-21
source: "trust-constr regressed 142.918 → 142.946 INFEAS on Ch2 small"
related: ["[[L-006-polish-warmstart-never-worse]]"]
effort_person_hours: 0.5
---

# L-010 — Interior-point / barrier methods need strictly-interior warm-starts

## The failure

After SLSQP joint polish improved Ch2 small to 142.918 d (feasible,
0.002 d below SLSQP basin), I tried trust-constr (scipy's
interior-point method) with the same warm-start, expecting stricter
constraint enforcement and possibly a deeper basin.

Result: 400 iters, status=0 (converged), but fun=142.946 d
(WORSE) and infeasible (chronology constraint violated by -1).

trust-constr regressed. The warm-start was at the boundary of
several constraints (Δv arcs at exactly the exception cap). The
interior-point barrier function diverges at the boundary, so the
algorithm pushes the iterate INWARD from the boundary — relaxing
exactly the constraints that were active. The relaxation made some
chronology constraints fail (sub-tour times re-shuffled).

## The lesson

**Barrier IP methods require a STRICTLY-INTERIOR warm-start.** If
the warm-start sits on the boundary of any inequality:
- The barrier function value is undefined (or huge) at start.
- The first iterate jumps inward to escape the barrier.
- That inward jump may violate other constraints (the "fix one,
  break another" problem).

## The fix

Two options:

1. **Use SLSQP / SQP instead.** SLSQP handles boundary points
   gracefully (it's a quadratic-programming SQP, not a barrier).
   SLSQP's slight slack on nonlinear constraints is the trade-off
   for accepting boundary warm-starts.
2. **Push warm-start interior FIRST.** Add a slack term to the
   warm-start by tightening each inequality by, e.g., 5e-4. Then
   warm-start trust-constr from that interior point. The barrier
   is finite there.

Example for our Ch2 small case:
```python
# Don't: warm-start at boundary
cap_per_leg = [dv_thr if not exc else dv_exc for leg]  # boundary
trust_constr(warm_start=banked_x, caps=cap_per_leg)    # regresses

# Do: shrink caps for interior warm-start
margin = 5e-4
cap_per_leg = [c - margin for c in cap_per_leg]        # interior
trust_constr(warm_start=banked_x, caps=cap_per_leg)    # works
```

This is exactly the `safety_margin` we used for SLSQP — but
trust-constr is MORE sensitive to it because of the barrier.

## When to use which

| | SLSQP | trust-constr |
|---|---|---|
| boundary warm-start | OK | regresses |
| nonlinear constraints | accepts, may slightly violate | enforces strictly |
| large problems | fast (O(n²) Hessian) | slower (O(n²) but more iters) |
| derivative-free | no | partial (with quasi-Newton Hessian) |

For our use case (96-var nonlinear with boundary warm-start), SLSQP
is the right tool. trust-constr would require a more careful warm-
start strategy.

## Generalization

Applies to any interior-point / barrier method:
- IPOPT (always needs interior init)
- KNITRO IP mode
- CVXPY's SCS/ECOS solvers
- Most LP barrier solvers (Gurobi barrier, HiGHS IPM)

Rule of thumb: if the docs warn about "feasibility of initial
point", read carefully.

## Impact / scope

~30 min trying trust-constr on Ch2 small. Codified to prevent the
same dead-end for Ch2 medium / large polish.
