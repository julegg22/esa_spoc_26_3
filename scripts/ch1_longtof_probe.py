"""E-707 — Ch1 trajectory: does EXTENDED tof reduce ΔV on the short high-ΔV transfers?
Audit found 214/400 transfers at dt<3d with mean ΔV 4303 (solver stuck near the min tof bound ~2.2d),
while the dt[3,10)d band has mean ΔV 2902. Decisive test: re-solve a sample of the short high-ΔV
transfers with tof extended to ~130d (low-energy regime the bounded solver never explores) and measure
the ΔV/mass change. If ΔV drops materially -> the low-energy long-coast architecture is the lever.
Usage: python ch1_longtof_probe.py [n_sample=10] [tof_ub=30]"""
import sys, json, time, math
import numpy as np
import pykep as pk
import pygmo as pg
from scipy.optimize import minimize
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/scripts")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, T as TUNIT
from ch1_backshoot_ecc import UDPBackEcc, official_row
ROOT = "/home/julian/Projects/esa_spoc_26_3"
TWO_PI = 2 * math.pi


class UDPLong(UDPBackEcc):
    """Same as UDPBackEcc but tof upper bound extended (explore the low-energy long-coast regime)."""
    def __init__(self, udp, idE, idL, tof_ub):
        super().__init__(udp, idE, idL); self.tof_ub = tof_ub

    def get_bounds(self):
        lb, ub = super().get_bounds(); ub = list(ub); ub[7] = self.tof_ub; return (lb, ub)


def solve_long(udp, idE, idL, idD, tof_ub, restarts=6, gen=200):
    prob = pg.problem(UDPLong(udp, idE, idL, tof_ub))
    lb, ub = prob.get_bounds(); lb = np.array(lb); ub = np.array(ub)
    cma = pg.algorithm(pg.cmaes(gen=gen, force_bounds=True, ftol=1e-7, xtol=1e-7))
    best = None
    for rs in range(restarts):
        rng = np.random.default_rng(7 * rs + idE * 5 + idL)
        pop = pg.population(prob, size=0)
        for _ in range(24):
            pop.push_back(lb + rng.random(8) * (ub - lb))
        pop = cma.evolve(pop)
        xb = pop.champion_x; fb = float(pop.champion_f[0])
        if fb < 1.3e4:
            res = minimize(lambda z: prob.fitness(z)[0], xb, method="Nelder-Mead",
                           options={"maxiter": 400, "fatol": 1e-3})
            if prob.fitness(res.x)[0] < fb:
                xb = res.x
            ov = official_row(udp, idE, idL, idD, xb)
            if ov is not None and ov[0] is not None and (best is None or ov[1] < best[1]):
                best = ov
    return best


def main(n_sample=10, tof_ub=30):
    udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    dv = json.load(open(f"{ROOT}/solutions/upload/trajectory.json"))[0]["decisionVector"]
    n = len(dv) // 21
    cands = []
    for i in range(n):
        r = dv[i * 21:i * 21 + 21]
        if r[0] < 0:
            continue
        DV = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
        dt = (r[19] + r[20]) * TUNIT * pk.SEC2DAY
        if dt < 3.0 and DV > 4000:                       # short + high-ΔV = the suspect set
            cands.append((DV, int(r[0]), int(r[1]), int(r[2])))
    cands.sort(reverse=True)
    rng = np.random.default_rng(0)
    samp = [cands[i] for i in rng.choice(len(cands), size=min(n_sample, len(cands)), replace=False)]
    print(f"[E-707] {len(cands)} short(<3d)+high-ΔV(>4000) transfers; sampling {len(samp)} with tof_ub={tof_ub} nondim (~{tof_ub*TUNIT*pk.SEC2DAY:.0f}d)", flush=True)
    t0 = time.time(); d_old = d_new = 0.0; wins = 0
    for (DV, e, l, d) in samp:
        res = solve_long(udp, e, l, d, tof_ub, restarts=6, gen=200)
        if res is None:
            print(f"  E{e},L{l}: cur ΔV={DV:.0f} -> long FAIL [{time.time()-t0:.0f}s]", flush=True); continue
        ndv = res[1]
        old_mass = np.exp(-DV / 311. / pk.G0) * 5000 - 500.
        new_mass = np.exp(-ndv / 311. / pk.G0) * 5000 - 500.
        d_old += DV; d_new += ndv; wins += (ndv < DV - 50)
        print(f"  E{e},L{l}: cur ΔV={DV:.0f} -> long ΔV={ndv:.0f} (Δ{ndv-DV:+.0f}; mass {old_mass:.0f}->{new_mass:.0f}) [{time.time()-t0:.0f}s]", flush=True)
    if d_old:
        print(f"\n[E-707] {wins}/{len(samp)} reduced ΔV; mean ΔV {d_old/len(samp):.0f} -> {d_new/len(samp):.0f} "
              f"(Δ{(d_new-d_old)/len(samp):+.0f}/transfer)", flush=True)
        if (d_old - d_new) / len(samp) > 200:
            print(f"[E-707] -> LONG-COAST reduces ΔV materially -> extended-tof fleet re-sweep is the lever toward rank-5/1.", flush=True)
        else:
            print(f"[E-707] -> long tof does NOT reduce ΔV; the short-transfer ΔV is near the BCP floor for these geometries.", flush=True)


if __name__ == "__main__":
    ns = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    tu = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    main(ns, tu)
