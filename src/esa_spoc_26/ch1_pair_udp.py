"""Per-pair pygmo UDP for Ch1 trajectory optimization (C-025 design).

Standard ESA/Izzo pattern: wrap the trajectory problem as a pygmo
User-Defined Problem and let pygmo's CMA-ES (or DE / BiteOpt) globally
optimize the 12 continuous dofs per (idE, idL) pair.

Decision vector (12 dofs):
  [raan_e, argp_e, ea_dep, t0, T1, T2,
   dv0_x, dv0_y, dv0_z, dv1_x, dv1_y, dv1_z]

dv2 is computed via solve_arrival_eccentric (no extra dofs).

Fitness = total dv (minimized). Pygmo minimizes; mass = exp(-dv/Isp/g0)·m0 − m_dry.

This replaces the position-match DC architecture with global optimization
over the full continuous space, which:
- Has no DC convergence issues (CMA-ES handles non-convex landscapes)
- Allows the optimizer to find apolune-burn configs naturally
- Treats raan_l/argp_l/ea_arr as FREE (solve_arrival_eccentric handles it)
"""
import numpy as np
import math

import pykep as pk
from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric


def _extract_earth_angles(pv0):
    """Recover (raan_e, argp_e, ea_dep) from a synodic pv0 on Earth orbit.

    Inverse of earth_orbit_state — converts synodic state to Earth-centered
    Keplerian (using state2earth's convention) and extracts the angles.
    """
    [x, y, z], [vx, vy, vz] = pv0
    rx = (x + CR3BP_MU_EARTH_MOON) * L
    ry = y * L
    rz = z * L
    vx_e = (vx - y) * V
    vy_e = ((vy + x) + CR3BP_MU_EARTH_MOON) * V
    vz_e = vz * V
    try:
        el = pk.ic2par([rx, ry, rz], [vx_e, vy_e, vz_e], MU_EARTH)
    except Exception:
        return 0.0, 0.0, 0.0
    # el = (a, e, i, raan, argp, eccentric_anomaly_or_mean_anomaly)
    return float(el[3]) % (2 * math.pi), \
           float(el[4]) % (2 * math.pi), \
           float(el[5]) % (2 * math.pi)

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3
ISP_G0 = 311.0 * 9.80665
M0 = 5000.0
M_DRY = 500.0


def _hohmann_dv0_synbasis(pv0):
    """Pure prograde Hohmann from LEO to Moon-distance apogee."""
    [x, y, z], [vx, vy, vz] = pv0
    rx, ry, rz = (x + MU) * L, y * L, z * L
    r0 = math.sqrt(rx * rx + ry * ry + rz * rz)
    vx_e, vy_e, vz_e = (vx - y) * V, ((vy + x) + MU) * V, vz * V
    v_mag = math.sqrt(vx_e * vx_e + vy_e * vy_e + vz_e * vz_e)
    a_t = (r0 + R_MOON_SI) / 2.0
    v_peri = math.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    scale = (v_peri - v_mag) / v_mag
    return [vx_e * scale / V, vy_e * scale / V, vz_e * scale / V]


PENALTY = 1e6  # Returned for infeasible / impactor / failed-LOI evaluations


class PairUDP:
    """pygmo UDP for a single (idE, idL) trajectory transfer.

    Constructed once per pair; pygmo calls .fitness(x) for each candidate.
    """

    def __init__(self, udp, idE, idL):
        self.udp = udp
        self.idE = idE
        self.idL = idL
        self.aE, self.eE, self.iE = udp.earth_data[idE]
        self.aL, self.eL, self.iL = udp.moon_data[idL]

    def fitness(self, x):
        (raan_e, argp_e, ea_dep, t0, T1, T2,
         dv0x, dv0y, dv0z, dv1x, dv1y, dv1z) = x

        # Bounds clamps (CMA-ES with force_bounds=True should respect, but safe-guard)
        if T1 < 0.05 or T2 < 0.0:
            return [PENALTY]

        try:
            pv0 = earth_orbit_state(self.aE, self.eE, self.iE,
                                      raan_e, argp_e, ea_dep)
        except Exception:
            return [PENALTY]

        # Propagate the 3-impulse trajectory
        try:
            pv_arr = propagate(pv0, t0,
                                [[dv0x, dv0y, dv0z],
                                 [dv1x, dv1y, dv1z],
                                 [0.0, 0.0, 0.0]],
                                [T1, T2])
        except Exception:
            return [PENALTY]
        if len(pv_arr) == 0:
            return [PENALTY]  # impactor

        # Compute dv2 via solve_arrival_eccentric (handles (a,e,i) match)
        res = solve_arrival_eccentric(pv_arr, self.aL, self.eL, self.iL)
        if res is None:
            return [PENALTY]
        dv2 = res[0]
        if not np.all(np.isfinite(dv2)):
            return [PENALTY]

        # Total dv (in m/s)
        dv0_mag = math.sqrt(dv0x * dv0x + dv0y * dv0y + dv0z * dv0z) * V
        dv1_mag = math.sqrt(dv1x * dv1x + dv1y * dv1y + dv1z * dv1z) * V
        dv2_mag = math.sqrt(dv2[0] ** 2 + dv2[1] ** 2 + dv2[2] ** 2) * V
        dv_total = dv0_mag + dv1_mag + dv2_mag

        if dv_total > 12000:  # Sanity: no transfer can use >12 km/s
            return [PENALTY]

        # Final fitness: minimize total dv (= maximize mass via rocket eq)
        return [dv_total]

    def get_bounds(self):
        TWO_PI = 2.0 * math.pi
        lb = [0.0, 0.0, 0.0, 0.0,         # raan_e, argp_e, ea_dep, t0
              0.05, 0.0,                   # T1 (min ~12 hr), T2 (>=0)
              -5.0, -5.0, -5.0,            # dv0 (nondim; ~5 → 5 km/s)
              -5.0, -5.0, -5.0]            # dv1
        ub = [TWO_PI, TWO_PI, TWO_PI, TWO_PI,
              7.0, 3.0,                    # T1 ≤ 30d (nondim), T2 ≤ 13d
              5.0, 5.0, 5.0,
              5.0, 5.0, 5.0]
        return (lb, ub)

    def get_name(self):
        return f"Ch1 transfer ({self.idE} → {self.idL})"


def hohmann_seed(udp, idE, idL, raan_e=0.0, argp_e=0.0, ea_dep=0.0,
                  t0=0.0, T1_d=5.0):
    """Build a seed chromosome: Hohmann dv0 from given phasing + dv1=0."""
    aE, eE, iE = udp.earth_data[idE]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    dv0 = _hohmann_dv0_synbasis(pv0)
    T1_seed = T1_d * 86400.0 / T
    return np.array([raan_e, argp_e, ea_dep, t0,
                      T1_seed, 0.0,
                      dv0[0], dv0[1], dv0[2],
                      0.0, 0.0, 0.0])


def bank_to_seed(udp, bank_row):
    """Convert a bank's 21-element row → PairUDP chromosome.

    Reverse-engineers (raan_e, argp_e, ea_dep) from bank's pv0 via
    state2earth + pk.ic2par, then bundles with bank's t0/T1/T2/dv0/dv1.
    """
    pv0 = [list(bank_row[4:7]), list(bank_row[7:10])]
    raan_e, argp_e, ea_dep = _extract_earth_angles(pv0)
    return np.array([raan_e, argp_e, ea_dep, float(bank_row[3]),
                      float(bank_row[19]), float(bank_row[20]),
                      float(bank_row[10]), float(bank_row[11]), float(bank_row[12]),
                      float(bank_row[13]), float(bank_row[14]), float(bank_row[15])])


def multi_seed_pop(prob, udp, idE, idL, pop_size=24, bank_row=None,
                    rng=None):
    """Build a diverse seed population for CMA-ES.

    Always includes:
    - Bank row's (raan=0, ea=0, t0=bank, dv0=bank, dv1=bank) if bank_row given
    - Hohmann seeds at multiple phasings (raan_e ∈ {0, π/2, π, 3π/2}, t0 ∈ {0, π})
    - Random fills to pop_size
    """
    if rng is None:
        rng = np.random.default_rng(idE * 1000 + idL)
    import pygmo as pg
    pop = pg.population(prob, size=0)
    lb, ub = prob.get_bounds()
    lb_a = np.array(lb)
    ub_a = np.array(ub)

    seeds = []
    if bank_row is not None:
        seeds.append(bank_to_seed(udp, bank_row))
    # Hohmann at multi-phasing
    for raan_e in (0.0, np.pi / 2, np.pi, 3 * np.pi / 2):
        for t0 in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                seeds.append(hohmann_seed(udp, idE, idL,
                                            raan_e=raan_e, ea_dep=ea_dep,
                                            t0=t0))
    # Clamp and push
    for s in seeds[:pop_size]:
        s = np.clip(s, lb_a, ub_a)
        pop.push_back(s)
    # Random fill
    while len(pop) < pop_size:
        x = lb_a + rng.random(len(lb_a)) * (ub_a - lb_a)
        pop.push_back(x)
    return pop


def chromosome_to_row(udp, x, idE, idL, idD=0):
    """Reconstruct the 21-element trajectory row from the UDP decision vector
    (for inclusion in the bank chromosome / UDP fitness verification)."""
    (raan_e, argp_e, ea_dep, t0, T1, T2,
     dv0x, dv0y, dv0z, dv1x, dv1y, dv1z) = x
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)
    pv_arr = propagate(pv0, t0,
                        [[dv0x, dv0y, dv0z],
                         [dv1x, dv1y, dv1z],
                         [0.0, 0.0, 0.0]],
                        [T1, T2])
    if len(pv_arr) == 0:
        return None
    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if res is None:
        return None
    dv2 = res[0]
    return [int(idE), int(idL), int(idD), float(t0),
            *[float(v) for v in pv0[0]], *[float(v) for v in pv0[1]],
            float(dv0x), float(dv0y), float(dv0z),
            float(dv1x), float(dv1y), float(dv1z),
            float(dv2[0]), float(dv2[1]), float(dv2[2]),
            float(T1), float(T2)]


def mass_from_row(udp, row):
    """Verify via UDP fitness; returns mass (kg) or 0 if invalid."""
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    return -f if f < 0 else 0.0


if __name__ == "__main__":
    import time
    import json
    import pygmo as pg
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Smoke test: 5 pairs, seeded from bank
    bank = json.load(open("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json"))
    dv = bank[0]["decisionVector"]
    bank_rows = {}
    for i in range(0, len(dv), 21):
        if dv[i] < 0:
            continue
        bank_rows[(int(dv[i]), int(dv[i + 1]))] = dv[i:i + 21]

    tests = [(8, 175), (38, 157), (244, 105), (21, 200), (213, 19)]
    for idE, idL in tests:
        bank_row = bank_rows.get((idE, idL))
        if bank_row is None:
            print(f"({idE}, {idL}): not in bank")
            continue
        bank_m = mass_from_row(udp, bank_row)
        prob = pg.problem(PairUDP(udp, idE, idL))

        # DE (sade is self-adaptive DE) — handles penalty landscapes well
        algo = pg.algorithm(pg.sade(gen=150, ftol=0.0, xtol=0.0))
        pop = multi_seed_pop(prob, udp, idE, idL, pop_size=30,
                              bank_row=bank_row)
        t_start = time.time()
        pop = algo.evolve(pop)
        dt = time.time() - t_start
        best_dv = pop.champion_f[0]
        best_x = pop.champion_x
        if best_dv > 1e5:
            print(f"  ({idE},{idL}): bank={bank_m:.0f} → SADE FAIL [{dt:.0f}s]")
        else:
            row = chromosome_to_row(udp, best_x, idE, idL)
            udp_m = mass_from_row(udp, row) if row else 0
            print(f"  ({idE},{idL}): bank={bank_m:.0f} → sade={udp_m:.0f} "
                  f"(Δ={udp_m - bank_m:+.0f}) [{dt:.0f}s]")
