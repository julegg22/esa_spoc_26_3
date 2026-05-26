"""Plane-change-at-apogee 3-impulse with PROPER PHASING.

The key insight (S-2026-05-26):
For Moon to be at the apogee position at TOF (the moment we apply dv1),
we need:
  raan_e + π = t0 + T1_hohmann (mod 2π)

The Hohmann half-period T1 depends on aE (Earth orbit semi-major).
For LEO: T1 ≈ 1.14 nondim. For GEO: T1 ≈ 1.27.

PHASING-AWARE raan_e:
  raan_e = t0 + T1_hohmann - π

This ensures spacecraft apogee aligns with Moon's position in inertial
frame at t = t0 + T1. Plane change burn at low velocity then works as
designed.
"""
import numpy as np
import pykep as pk
from scipy.optimize import least_squares

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, MU_MOON, CR3BP_MU_EARTH_MOON,
    earth_orbit_state, moon_orbit_state, propagate,
)
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def hohmann_half_period_nondim(aE):
    """Half-period of Hohmann transfer from aE to Moon distance (nondim)."""
    a_trans = (aE + R_MOON_SI) / 2
    T1_sec = np.pi * np.sqrt(a_trans**3 / MU_EARTH)
    return T1_sec / T


def try_proper_apogee_3impulse(udp, idE, idL, argp_e, ea_dep,
                                  raan_l, argp_l, ea_arr, t0, t2_d=2.0,
                                  raan_offset=0.0):
    """3-impulse with PROPER per-pair phasing.

    raan_e = t0 + T1_hohmann - π + raan_offset

    raan_offset allows fine-tuning around the nominal phasing.
    """
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]

    # PROPER PHASING — compute raan_e
    T1 = hohmann_half_period_nondim(aE)
    raan_e = (t0 + T1 - np.pi + raan_offset) % (2 * np.pi)

    pv0 = earth_orbit_state(aE, eE, iE, raan_e, argp_e, ea_dep)

    # Compute pure prograde dv0 = Hohmann burn in Earth orbit's tilted plane
    # We need v0 in inertial. At t0=0, synodic axes = inertial axes (within nondim
    # rotation by t0). For consistency with the phasing computation, treat as if
    # synodic = inertial at the spacecraft's start time (the BCP code propagates
    # forward from time t0).
    x, y, z = pv0[0]
    vx, vy, vz = pv0[1]
    # Synodic position → inertial position (assuming aligned at start time)
    r_syn = np.array([x + MU, y, z])  # Earth-centered, in synodic axes at start
    v_syn_inertial = np.array([vx - y, vy + (x + MU), vz])
    # For computing dv0 magnitude (and direction):
    r_inertial = r_syn  # at start, axes coincide
    v_inertial = v_syn_inertial
    r_n = np.linalg.norm(r_inertial) * L
    v_mag = np.linalg.norm(v_inertial) * V

    a_trans = (r_n + R_MOON_SI) / 2
    v_peri_trans = np.sqrt(MU_EARTH * (2.0 / r_n - 1.0 / a_trans))
    # dv0 in direction of v0 (pure prograde):
    dv0_si = v_inertial * V * ((v_peri_trans - v_mag) / v_mag)
    dv0_syn = dv0_si / V

    if not np.all(np.isfinite(dv0_syn)) or np.linalg.norm(dv0_syn) > 8:
        return None

    T2 = t2_d * 86400.0 / T

    # Propagate to apogee
    pv_apogee = propagate(pv0, t0, [dv0_syn.tolist(), [0, 0, 0], [0, 0, 0]],
                           [T1, 0.0])
    if len(pv_apogee) == 0:
        return None

    # Target arrival point on Moon orbit
    pv_tgt = moon_orbit_state(aL, eL, iL, raan_l, argp_l, ea_arr)

    # DC on dv1 to match arrival position after T2
    def residual(dv1):
        pv_arr = propagate(pv_apogee, t0 + T1,
                            [[0, 0, 0], dv1.tolist(), [0, 0, 0]],
                            [0.0, T2])
        if len(pv_arr) == 0:
            return [100.0] * 3
        return [pv_arr[0][0] - pv_tgt[0][0],
                pv_arr[0][1] - pv_tgt[0][1],
                pv_arr[0][2] - pv_tgt[0][2]]

    try:
        sol = least_squares(residual, np.zeros(3), method="trf",
                             xtol=1e-12, ftol=1e-12, max_nfev=80)
    except Exception:
        return None
    dv1_syn = sol.x
    if not np.all(np.isfinite(dv1_syn)) or np.linalg.norm(dv1_syn) > 5:
        return None

    pv_arr = propagate(pv_apogee, t0 + T1,
                        [[0, 0, 0], dv1_syn.tolist(), [0, 0, 0]],
                        [0.0, T2])
    if len(pv_arr) == 0:
        return None
    dv2_res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
    if dv2_res is None:
        return None
    dv2_syn, _ = dv2_res

    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
            *dv0_syn.tolist(), *dv1_syn.tolist(), *dv2_syn.tolist(),
            T1, T2]
    chr_padded = list(row)
    pad = (udp.dim - len(chr_padded)) // 21
    for _ in range(pad):
        chr_padded.extend([-1.0] + [0.0] * 20)
    f = udp.fitness(chr_padded)[0]
    if f >= 0:
        return None
    mass = -f
    dv_ms = (np.linalg.norm(dv0_syn) + np.linalg.norm(dv1_syn)
              + np.linalg.norm(dv2_syn)) * V
    return mass, row, dv_ms


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    test_cases = [
        (0, 0, "coplanar control"),
        (213, 19, "LEO+iL=1.07"),
        (303, 109, "LEO+iL=1.08"),
        (244, 105, "LEO+iL=0.50"),
        (227, 315, "LEO+iL=0.47"),
    ]

    print("Testing PROPER PHASING apogee 3-impulse:", flush=True)
    print(f"{'pair':>10} {'desc':<22} {'mass':>5} {'dv0':>5} {'dv1':>5} {'dv2':>5} {'tot':>5}",
          flush=True)
    for idE, idL, desc in test_cases:
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        T1 = hohmann_half_period_nondim(aE)
        T1_days = T1 * T / 86400.0
        t_start = time.time()
        best = None
        # Sweep argp_e, ea_dep, raan_offset (fine-tune around computed raan_e),
        # ea_arr, t0, t2_d
        for argp_e in (0.0, np.pi):
            for ea_dep in (0.0, np.pi):
                for raan_offset in np.linspace(-0.5, 0.5, 5):
                    for ea_arr in np.linspace(0, 2 * np.pi, 4, endpoint=False):
                        for t0_val in (0.0, np.pi, 2 * np.pi):
                            for t2_d in (0.1, 0.3, 0.5, 0.8):  # SHORT T2: stay inside Moon SOI
                                res = try_proper_apogee_3impulse(
                                    udp, idE, idL, argp_e, ea_dep,
                                    0.0, 0.0, ea_arr, t0_val, t2_d,
                                    raan_offset=raan_offset)
                                if res is not None and (best is None
                                                          or res[0] > best[0]):
                                    best = res
        dt = time.time() - t_start
        if best:
            mass, row, dv_tot = best
            dv0 = np.sqrt(row[10]**2+row[11]**2+row[12]**2) * V
            dv1 = np.sqrt(row[13]**2+row[14]**2+row[15]**2) * V
            dv2 = np.sqrt(row[16]**2+row[17]**2+row[18]**2) * V
            print(f"  ({idE:>3},{idL:>3}) {desc:<22} {mass:>5.0f} "
                  f"{dv0:>5.0f} {dv1:>5.0f} {dv2:>5.0f} {dv_tot:>5.0f} "
                  f"T1={T1_days:.1f}d ({dt:.0f}s)", flush=True)
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<22} FAIL ({dt:.0f}s)",
                  flush=True)
