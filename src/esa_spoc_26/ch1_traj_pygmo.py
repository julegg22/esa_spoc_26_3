"""H-002 timeboxed global-trajopt attempt (T-005 / user 2026-05-19).

Stiff geometric shooting (E-006..E-011) finds geometry-valid but
ΔV-pathological transfers. Here a global optimiser (pygmo) drives the
backward-construction params with the **official fitness as objective**
— fitness already encodes ΔV→mass and the 200-day time discount, so
minimising it intrinsically seeks low-ΔV, long Sun-assisted captures.
Reuses the validated pipeline (T-005: the pipeline is the asset).

decision vector (single (idE,idL) transfer):
  [tof_days, t_arr, OmM, nuM, dv2x, dv2y, dv2z]   (dv2 in m/s)
"""

from __future__ import annotations

import numpy as np

from esa_spoc_26.ch1_trajectory import (
    LtlTrajectory,
    V,
    moon_orbit_state,
)
from esa_spoc_26.ch1_trajectory import T as _T
from esa_spoc_26.ch1_trajectory_solve import (
    _back_state,
    solve_departure_dv,
)

DAY = 86400.0


class TransferUDP:
    """pygmo UDP: one (idE,idL) BCP transfer scored by the official
    fitness (negated mass; pygmo minimises ⇒ seeks positive mass)."""

    def __init__(self, udp: LtlTrajectory, idE: int, idL: int):
        self.udp = udp
        self.idE = idE
        self.idL = idL
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aL, self.eL, self.iL = udp.moon_data[idL]

    def get_bounds(self):
        lo = [2.0, 0.0, 0.0, 0.0, -1500.0, -1500.0, -1500.0]
        hi = [150.0, 50.0, 2 * np.pi, 2 * np.pi, 1500.0, 1500.0, 1500.0]
        return (lo, hi)

    def fitness(self, x):
        tof = x[0] * DAY / _T
        t_arr = x[1]
        arr = moon_orbit_state(self.aL, self.eL, self.iL, x[2], 0.0, x[3])
        dv2 = np.array(x[4:7]) / V
        S0 = arr[0]
        S1 = [arr[1][0] - dv2[0], arr[1][1] - dv2[1], arr[1][2] - dv2[2]]
        D = _back_state(S0, S1, t_arr, tof)
        if D is None:
            return [1e7]
        dep = solve_departure_dv(
            [[D[0], D[1], D[2]], [D[3], D[4], D[5]]],
            self.aE, self.eE, self.iE,
        )
        if dep is None:
            return [1e6]
        posvel0, dv0, _ = dep
        row = [self.idE, self.idL, 0, t_arr - tof, *posvel0[0], *posvel0[1],
               *dv0, 0.0, 0.0, 0.0, *dv2.tolist(), float(tof), 0.0]
        f = self.udp.fitness(row)[0]      # official: negated mass
        return [f if np.isfinite(f) else 1e7]


def run(idE=0, idL=0, gens=60, pop=40, seed=0):
    import pygmo as pg

    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    prob = pg.problem(TransferUDP(udp, idE, idL))
    algo = pg.algorithm(pg.sade(gen=gens, ftol=1e-8, xtol=1e-8, seed=seed))
    algo.set_verbosity(10)
    pop_ = pg.population(prob, pop, seed=seed)
    pop_ = algo.evolve(pop_)
    best = pop_.champion_f[0]
    mass = -best if best < 0 else 0.0
    print(f"H-002 pygmo E{idE}->M{idL}: champion fitness={best:.3f} "
          f"-> delivered mass={mass:.1f} kg "
          f"({'POSITIVE — valid scoring transfer' if mass > 0 else 'still non-positive'})")
    return pop_.champion_x, best


if __name__ == "__main__":
    import sys

    g = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    run(gens=g)
