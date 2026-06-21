"""Diagnostic: WHY does a sub-bank search candidate fail the 384m/1e-6 official window?
Run 1 CMA restart on (241,50), take the feasible candidate, report the match residual (a,e,i errors)
before and after the precise DC, and the official accept/reject. Isolates the precision blocker."""
import sys, numpy as np
sys.path.insert(0, "src")
import importlib.util
spec = importlib.util.spec_from_file_location("m", "scripts/ch1_minenergy_solver.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
import pygmo as pg
from esa_spoc_26.ch1_trajectory import earth_orbit_state, state2moon, L

udp = m.LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
e, l = 241, 50
aM, eM, iM = udp.moon_data[l]
print(f"target Moon orbit: aM={aM:.3e} m  eM={eM:.5f}  iM={np.degrees(iM):.3f}deg")
prob = pg.problem(m.UDP(udp, e, l, 16.0))
lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
cma = pg.algorithm(pg.cmaes(gen=200, force_bounds=True))
rng = np.random.default_rng(123)
pop = pg.population(prob, size=0)
for _ in range(22):
    pop.push_back(lb + rng.random(7) * (ub - lb))
pop = cma.evolve(pop)
xb = pop.champion_x; fb = float(pop.champion_f[0])
print(f"CMA champion feas_dv (1e-12) = {fb:.0f}")


def match_err(x, label):
    aE, eE, iE = udp.earth_data[e]
    pv0 = earth_orbit_state(aE, eE, iE, x[0], x[1], x[2])
    st, peri, pt = m.prop_to_peri(pv0, x[3], x[4:7], 16.0, fast=False)
    if st is None:
        print(f"  {label}: impact"); return
    print(f"  {label}: perilune r={peri*L:.3e} m (target {aM:.3e}, miss {abs(peri*L-aM)/1000:.1f}km)")
    a2 = m.solve_arrival_dv(st, aM, eM, iM)
    if a2 is None:
        print(f"    solve_arrival_dv: None (radius outside window)"); return
    final = [st[0], [st[1][i] + a2[0][i] for i in range(3)]]
    el = state2moon(final)
    print(f"    post-insertion: a={el[0]:.3e}(err {abs(el[0]-aM):.1f}m, tol 384m) "
          f"e={el[1]:.5f}(err {abs(el[1]-eM):.2e}, tol 1e-6) i_err={abs(el[2]-iM):.2e}(tol 1e-6)")
    ov = m.official_row(udp, e, l, x, 16.0)
    print(f"    OFFICIAL: {'VALID dv=%.0f' % ov[1] if ov else 'REJECTED'}")


match_err(xb, "raw candidate")
xf = m.precise_dc(udp, e, l, xb, 16.0)
match_err(xf, "after precise_dc")
