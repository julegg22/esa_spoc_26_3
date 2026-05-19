"""Ch1 trajectory-matching — faithful mirror of the OFFICIAL UDP.

Source of truth: the competition UDP served via GraphQL `udpFile`
(reference/spoc4_udp/trajectory-matching.py, fetched 2026-05-19 —
see [[L-002]] / [[O-004]]). The git starter kit ships no Ch1 Python;
the README's BCP constants are WRONG (μ_s) — only this UDP is valid.

This module reproduces the official BCP dynamics, `propagate`,
`state2earth`/`state2moon`, and the `fitness` oracle, parameterised
by the local data path, so the H-002 transfer/assignment optimiser
can score candidates against the exact server objective. Keep this
byte-faithful to the official UDP; do not "improve" the physics.
"""

from __future__ import annotations

import sys
from copy import deepcopy

import heyoka as hy
import numpy as np
import pykep as pk

# --- official constants (UDP lines 7-17) ---
L = 3.84405000e8
T = 3.7567696752e5
V = L / T
MU_SUN = 1.32712440041279419e20
MU_EARTH = 398600435507000.0
MU_MOON = 4902800118000.0
CR3BP_MU_EARTH_MOON = MU_MOON / (MU_MOON + MU_EARTH)
BCP_MU_S = MU_SUN / (MU_MOON + MU_EARTH)
BCP_RHO_S = 3.88811143e2
BCP_OMEGA_S = -9.25195985e-01
HORIZON_DAYS = 200.0


def bcp_dyn():
    x, y, z, vx, vy, vz = hy.make_vars("x", "y", "z", "vx", "vy", "vz")
    mu, mu_sun, rho_sun, omega_sun = hy.par[0], hy.par[1], hy.par[2], hy.par[3]
    r1 = hy.sqrt((x + mu) ** 2 + y**2 + z**2)
    r2 = hy.sqrt((x - (1 - mu)) ** 2 + y**2 + z**2)
    x_sun = rho_sun * hy.cos(omega_sun * hy.time)
    y_sun = rho_sun * hy.sin(omega_sun * hy.time)
    r_sun = hy.sqrt((x - x_sun) ** 2 + (y - y_sun) ** 2 + z**2)
    vxdot = (2 * vy + x - (1 - mu) * (x + mu) / r1**3
             - mu * (x + mu - 1) / r2**3
             - mu_sun / r_sun**3 * (x - x_sun)
             - mu_sun / rho_sun**2 * hy.cos(omega_sun * hy.time))
    vydot = (-2 * vx + y - (1 - mu) * y / r1**3 - mu * y / r2**3
             - mu_sun / r_sun**3 * (y - y_sun)
             - mu_sun / rho_sun**2 * hy.sin(omega_sun * hy.time))
    vzdot = -(1 - mu) * z / r1**3 - mu * z / r2**3 - mu_sun / r_sun**3 * z
    return [(x, vx), (y, vy), (z, vz), (vx, vxdot), (vy, vydot), (vz, vzdot)]


def state2earth(posvel):
    [x, y, z], [vx, vy, vz] = posvel
    vx_EF = (vx - y) * V
    vy_EF = (vy + x) * V
    vz_EF = vz * V
    vy_EF = vy_EF - (-CR3BP_MU_EARTH_MOON) * V
    x_EF = (x + CR3BP_MU_EARTH_MOON) * L
    y_EF = y * L
    z_EF = z * L
    return pk.ic2par([x_EF, y_EF, z_EF], [vx_EF, vy_EF, vz_EF], MU_EARTH)[:3]


def state2moon(posvel):
    [x, y, z], [vx, vy, vz] = posvel
    vx_MF = (vx - y) * V
    vy_MF = (vy + x) * V
    vz_MF = vz * V
    vy_MF = vy_MF - (1.0 - CR3BP_MU_EARTH_MOON) * V
    x_MF = (x - 1 + CR3BP_MU_EARTH_MOON) * L
    y_MF = y * L
    z_MF = z * L
    return pk.ic2par([x_MF, y_MF, z_MF], [vx_MF, vy_MF, vz_MF], MU_MOON)


def earth_orbit_state(a_e, e_e, i_e, raan, argp, ea):
    """Synodic BCP state lying exactly on the Earth orbit (a_e,e_e,i_e)
    [SI]. Exact inverse of `state2earth` (free knobs: raan, argp, EA).
    Round-trips through state2earth/_match_orbit to machine precision."""
    r, v = pk.par2ic([a_e, e_e, i_e, raan, argp, ea], MU_EARTH)
    x, y, z = r[0] / L - CR3BP_MU_EARTH_MOON, r[1] / L, r[2] / L
    vx = v[0] / V + y
    vy = v[1] / V - CR3BP_MU_EARTH_MOON - x
    vz = v[2] / V
    return [[x, y, z], [vx, vy, vz]]


def moon_orbit_state(a_m, e_m, i_m, raan, argp, ea):
    """Synodic BCP state lying exactly on the Moon orbit (a_m,e_m,i_m)
    [SI]. Exact inverse of `state2moon` (the arrival target family)."""
    r, v = pk.par2ic([a_m, e_m, i_m, raan, argp, ea], MU_MOON)
    x = r[0] / L + 1.0 - CR3BP_MU_EARTH_MOON
    y, z = r[1] / L, r[2] / L
    vx = v[0] / V + y
    vy = v[1] / V + (1.0 - CR3BP_MU_EARTH_MOON) - x
    vz = v[2] / V
    return [[x, y, z], [vx, vy, vz]]


def propagate(posvel, t0, DVs, Ts):
    x, y, z = hy.make_vars("x", "y", "z")  # only x,y,z used in event exprs
    dyn = bcp_dyn()
    earth_impacts, moon_impacts = [], []

    def cb_E(ta, time, d_sgn):
        earth_impacts.append(time)

    ev_E = hy.nt_event(
        (x + hy.par[0]) ** 2 + y**2 + z**2
        - (pk.EARTH_RADIUS + 99000) ** 2 / L**2,
        callback=cb_E,
    )

    def cb_M(ta, time, d_sgn):
        moon_impacts.append(time)

    ev_M = hy.nt_event(
        (x - 1 + hy.par[0]) ** 2 + y**2 + z**2
        - (1737400.0 + 30000) ** 2 / L**2,
        callback=cb_M,
    )
    ta = hy.taylor_adaptive(dyn, tol=1e-16, nt_events=[ev_E, ev_M])
    ta.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
    ta.time = t0
    pv = deepcopy(posvel)
    pv[1][0] += DVs[0][0]
    pv[1][1] += DVs[0][1]
    pv[1][2] += DVs[0][2]
    ta.state[:6] = pv[0] + pv[1]
    for i, tt in enumerate(Ts):
        ta.propagate_for(tt)
        ta.state[3] += DVs[i + 1][0]
        ta.state[4] += DVs[i + 1][1]
        ta.state[5] += DVs[i + 1][2]
    if earth_impacts or moon_impacts:
        return []
    return [list(ta.state[:3]), list(ta.state[3:6])]


class LtlTrajectory:
    """Official `ltl` UDP, local-path parameterised. fitness(x) returns
    [-tomatoe_mass] (negated, as scored); [0] on any invalid transfer."""

    dim = 8400

    def __init__(self, data_dir):
        d = data_dir if data_dir.endswith("/") else data_dir + "/"
        self.earth_data = np.loadtxt(d + "Earth_orbits.txt", skiprows=1)[:, 1:]
        self.moon_data = np.loadtxt(d + "Moon_orbits.txt", skiprows=1)[:, 1:]
        ltl_data = np.loadtxt(d + "LTL.txt", skiprows=1)
        self.ltl_dict = {(int(a), int(b)): w for a, b, w in ltl_data}

    def _real_tomatoe_mass(self, idl, idd, mass, dt):
        cld = self.ltl_dict[(int(idl), int(idd))]
        return (HORIZON_DAYS - dt) * cld if (HORIZON_DAYS - dt) * cld < mass else mass

    def _match_orbit(self, el, a, e, i):
        return (abs(el[0] - a) / L < 1e-6) and (abs(el[1] - e) < 1e-6) \
            and (abs(el[2] - i) < 1e-6)

    def _validate_transfer(self, idE, idL, t0, posvel, DVs, Ts):
        pv0 = deepcopy(posvel)
        aE, eE, iE = self.earth_data[idE]
        aL, eL, iL = self.moon_data[idL]
        if not self._match_orbit(state2earth(pv0), aE, eE, iE):
            return False
        pv1 = propagate(pv0, t0, DVs, Ts)
        if len(pv1) == 0:
            return False
        if not self._match_orbit(state2moon(pv1), aL, eL, iL):
            return False
        dv = sum(np.sqrt(D[0] ** 2 + D[1] ** 2 + D[2] ** 2) for D in DVs) * V
        return dv, sum(Ts) * T * pk.SEC2DAY

    def fitness(self, x):
        sol = np.array(x)
        if len(sol) % 21 != 0:
            return [0]
        sol = sol.reshape(-1, 21)
        matching, total = [], 0.0
        for ln in sol:
            (ide, idl, idd, t0, x0, y0, z0, vx0, vy0, vz0,
             d00, d01, d02, d10, d11, d12, d20, d21, d22, T1, T2) = ln
            if ide < 0:
                continue
            matching.append((int(ide), int(idl), int(idd)))
            res = self._validate_transfer(
                int(ide), int(idl), t0,
                [[x0, y0, z0], [vx0, vy0, vz0]],
                [[d00, d01, d02], [d10, d11, d12], [d20, d21, d22]],
                [T1, T2],
            )
            if res is False:
                return [0]
            dv, dt = res
            mass = np.exp(-dv / 311.0 / pk.G0) * 5000 - 500.0
            total += self._real_tomatoe_mass(idl, idd, mass, dt)
        used_e, used_l, used_d = set(), set(), set()
        for e, m, dd in matching:
            if e in used_e or m in used_l or dd in used_d:
                return [0]
            used_e.add(e)
            used_l.add(m)
            used_d.add(dd)
        return [-float(total)]

    def get_bounds(self):
        return ([0, 0, 0] + [-sys.maxsize / 2] * (self.dim - 3),
                [400, 400, 400] + [sys.maxsize / 2] * (self.dim - 3))


if __name__ == "__main__":
    base = "reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
    udp = LtlTrajectory(base)
    print(f"constants: mu={CR3BP_MU_EARTH_MOON:.12f} "
          f"mu_s={BCP_MU_S:.6f} (README said 3.3294e5)")
    print("earth", udp.earth_data.shape, "moon", udp.moon_data.shape,
          "ltl_dict", len(udp.ltl_dict))
    print("empty solution fitness:", udp.fitness([-1] + [0.0] * 20))

    # round-trip: state on Earth/Moon orbit 0 must re-derive its (a,e,i)
    aE, eE, iE = udp.earth_data[0]
    pv = earth_orbit_state(aE, eE, iE, 0.4, 1.1, 0.7)
    el = state2earth(pv)
    print(f"Earth round-trip: target=({aE:.3f},{eE:.3e},{iE:.3e}) "
          f"got=({el[0]:.3f},{el[1]:.3e},{el[2]:.3e}) "
          f"match={udp._match_orbit(el, aE, eE, iE)}")
    aM, eM, iM = udp.moon_data[0]
    pv = moon_orbit_state(aM, eM, iM, 0.4, 1.1, 0.7)
    el = state2moon(pv)
    print(f"Moon  round-trip: target=({aM:.3f},{eM:.3e},{iM:.3e}) "
          f"got=({el[0]:.3f},{el[1]:.3e},{el[2]:.3e}) "
          f"match={udp._match_orbit(el, aM, eM, iM)}")
