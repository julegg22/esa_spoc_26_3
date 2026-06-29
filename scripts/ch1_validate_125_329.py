"""E-757 decisive: mass-validate the known ΔV-winner (125,329) at the REAL idD. Forced-test showed
ΔV 4799->4126 @36d; does that convert to a bankable MASS gain (cargo non-binding)? Single pair, CMA.
Usage: python ch1_validate_125_329.py"""
import json, sys, time
import numpy as np
import pygmo as pg
sys.path.insert(0, "scripts"); sys.path.insert(0, "src")
from ch1_moderate_forced_test import UDPModerate
from ch1_backshoot_ecc import UDPBackEcc, solve_departure_dv_ecc
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]; N = len(bank) // 21
idE, idL = 125, 329
br = None
for i in range(N):
    r = bank[i * 21:(i + 1) * 21]
    if int(r[0]) == idE and int(r[1]) == idL:
        br = r; break
idD = int(br[2]); f = udp.fitness(br)[0]; cur = -f if f < 0 else 0
bdv = (np.linalg.norm(br[10:13]) + np.linalg.norm(br[13:16]) + np.linalg.norm(br[16:19])) * V
print(f"(125,329,D={idD}) bank mass={cur:.0f} dvtot={bdv:.0f}", flush=True)
prob = pg.problem(UDPModerate(udp, idE, idL)); cma = pg.algorithm(pg.cmaes(gen=250, force_bounds=True, ftol=1e-7))
lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub); rng = np.random.default_rng(7); best = None
t0 = time.time()
for _ in range(10):
    pop = pg.population(prob, 0)
    for _i in range(20): pop.push_back(lb + rng.random(8) * (ub - lb))
    pop = cma.evolve(pop)
    if best is None or float(pop.champion_f[0]) < best[0]: best = (float(pop.champion_f[0]), pop.champion_x)
prob2 = UDPBackEcc(udp, idE, idL); S, dv2, t_arr, tof, D = prob2._back(best[1])
ds = [[D[0], D[1], D[2]], [D[3], D[4], D[5]]]; dep = solve_departure_dv_ecc(ds, prob2.aE, prob2.eE, prob2.iE)
p0, dv0, _ = dep
row = [idE, idL, idD, float(t_arr - tof), *p0[0], *p0[1], *np.asarray(dv0).tolist(), 0, 0, 0,
       *np.asarray(dv2).tolist(), float(tof), 0.0]
ff = udp.fitness(row)[0]; mass = -ff if ff < 0 else None
rdv = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
print(f"moderate(real idD): mass={'INVALID' if mass is None else f'{mass:.0f}'} dvtot={rdv:.0f} dt={row[19]+row[20]:.1f}d "
      f"{'<<MASS WIN +%.0f' % (mass-cur) if (mass and mass>cur+5) else ''} [{time.time()-t0:.0f}s]", flush=True)
