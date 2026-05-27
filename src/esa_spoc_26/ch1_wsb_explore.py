"""WSB / long-TOF exploration — first phase of Sun-assist pivot.

The leaderboard's 3320 m/s average dv-per-transfer is ~620 m/s BELOW
the impulsive Hohmann+LOI minimum (3940 m/s). This signals competitors
exploit BCP's solar gravity for low-energy transfers (Belbruno-Miller-
style ballistic capture).

This module is an *experimental probe* — find out empirically whether:
(a) Multi-rev BCP trajectories with TOF up to 120 days yield lower
    Moon-relative arrival velocity than direct Hohmann.
(b) `solve_arrival_eccentric` gives dv2 ≈ 0 for "ballistic capture"-
    like arrival states (= already near the target orbit's energy).

For each (idE, idL), apply a *grid* of dv0 perturbations from the
Hohmann nominal (smaller, larger, off-axis), propagate 60–120 days,
scan trajectory for perilune/apolune events, and at each event try
`solve_arrival_eccentric`. Report best.

This is NOT a production solver — it's a research probe to identify
which (idE, idL) pairs benefit from WSB physics.
"""
import numpy as np

from esa_spoc_26.ch1_trajectory import (
    L, T, V, MU_EARTH, CR3BP_MU_EARTH_MOON,
    earth_orbit_state,
)
from esa_spoc_26.ch1_trajectory_solve import _ta
from esa_spoc_26.ch1_arrival_v2 import solve_arrival_eccentric

MU = CR3BP_MU_EARTH_MOON
R_MOON_SI = 384400e3


def _hohmann_dv0(pv0):
    """Synodic-basis prograde Hohmann burn (no R(t) rotation)."""
    [x, y, z], [vx, vy, vz] = pv0
    rx, ry, rz = (x + MU) * L, y * L, z * L
    r0 = np.sqrt(rx ** 2 + ry ** 2 + rz ** 2)
    vx_e, vy_e, vz_e = (vx - y) * V, ((vy + x) + MU) * V, vz * V
    v_mag = np.sqrt(vx_e ** 2 + vy_e ** 2 + vz_e ** 2)
    a_t = (r0 + R_MOON_SI) / 2
    v_peri = np.sqrt(MU_EARTH * (2.0 / r0 - 1.0 / a_t))
    scale = (v_peri - v_mag) / v_mag
    return np.array([vx_e * scale, vy_e * scale, vz_e * scale]) / V


def scan_perilune_events(pv0, t0, dv0, t_max_d, dt_d=0.5):
    """Walk BCP trajectory, return (t_d, state) at each LOCAL perilune
    (= local minimum of r_moon(t))."""
    ta = _ta()
    ta.time = t0
    ta.state[0] = pv0[0][0]
    ta.state[1] = pv0[0][1]
    ta.state[2] = pv0[0][2]
    ta.state[3] = pv0[1][0] + dv0[0]
    ta.state[4] = pv0[1][1] + dv0[1]
    ta.state[5] = pv0[1][2] + dv0[2]

    t_max_nondim = t_max_d * 86400.0 / T
    dt_nondim = dt_d * 86400.0 / T
    n = int(t_max_nondim / dt_nondim) + 1
    R_EARTH_2 = ((6378e3 + 99000) / L) ** 2
    R_MOON_2 = ((1737400 + 30000) / L) ** 2

    events = []  # list of (t_nondim_from_t0, state6, r_moon_nondim)
    r_hist = []
    for k in range(1, n + 1):
        try:
            ta.propagate_until(t0 + k * dt_nondim)
        except Exception:
            break
        x, y, z = ta.state[0], ta.state[1], ta.state[2]
        if (x + MU) ** 2 + y * y + z * z < R_EARTH_2:
            break
        if (x - 1 + MU) ** 2 + y * y + z * z < R_MOON_2:
            break
        r = np.sqrt((x - 1 + MU) ** 2 + y * y + z * z)
        r_hist.append((k, r, ta.state.copy()))

    # Find local minima in r_hist
    if len(r_hist) < 3:
        return events
    for i in range(1, len(r_hist) - 1):
        if r_hist[i][1] < r_hist[i - 1][1] and r_hist[i][1] < r_hist[i + 1][1]:
            t_d = r_hist[i][0] * dt_d
            events.append((t_d, r_hist[i][2], r_hist[i][1]))
    return events


def probe_pair(udp, idE, idL, ea_dep_grid=(0, np.pi/2, np.pi, 3*np.pi/2),
                t0_grid=(0.0, np.pi), dv0_scale_grid=(0.95, 0.97, 0.99, 1.0, 1.01, 1.03),
                t_max_d=100.0):
    """Multi-rev probe for one pair. Returns best (mass, row, dv_ms, tof_d)."""
    aE, eE, iE = udp.earth_data[idE]
    aL, eL, iL = udp.moon_data[idL]
    best = None

    for ea_dep in ea_dep_grid:
        pv0 = earth_orbit_state(aE, eE, iE, 0.0, 0.0, ea_dep)
        dv0_nominal = _hohmann_dv0(pv0)
        if not np.all(np.isfinite(dv0_nominal)):
            continue
        for t0 in t0_grid:
            for scale in dv0_scale_grid:
                dv0 = dv0_nominal * scale
                if np.linalg.norm(dv0) > 8:
                    continue
                events = scan_perilune_events(pv0, t0, dv0.tolist(), t_max_d)
                for t_d, state, r_min_nd in events:
                    pv_arr = [list(state[:3]), list(state[3:6])]
                    res = solve_arrival_eccentric(pv_arr, aL, eL, iL)
                    if res is None:
                        continue
                    dv2, _ = res
                    if not np.all(np.isfinite(dv2)) or np.linalg.norm(dv2) > 5:
                        continue
                    T1 = t_d * 86400.0 / T
                    row = [idE, idL, 0, t0, *pv0[0], *pv0[1],
                            *dv0.tolist(), 0.0, 0.0, 0.0, *dv2.tolist(),
                            T1, 0.0]
                    chr_p = list(row)
                    pad = (udp.dim - len(chr_p)) // 21
                    for _ in range(pad):
                        chr_p.extend([-1.0] + [0.0] * 20)
                    f = udp.fitness(chr_p)[0]
                    if f >= 0:
                        continue
                    mass = -f
                    dv_ms = (np.linalg.norm(dv0) + np.linalg.norm(dv2)) * V
                    if best is None or mass > best[0]:
                        best = (mass, row, dv_ms, t_d)
    return best


if __name__ == "__main__":
    import time
    from esa_spoc_26.ch1_trajectory import LtlTrajectory
    udp = LtlTrajectory("/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")

    # Test pairs — focus on LEO+LMO where Hohmann gives ~800 kg and WSB
    # could push to 1200+
    test_cases = [
        (0, 0, "LEO+LMO coplanar (bank 819)"),
        (1, 1, "LEO+LMO eL=0 (?)"),
        (10, 50, "LEO+LMO mid (?)"),
        (244, 105, "LEO+iL=0.50 (bank 374)"),
        (21, 200, "LEO+high-eL (bank 1095)"),
    ]
    print(f"WSB probe (t_max=100d, multi-rev, dv0 scale grid):")
    print(f"{'pair':>10} {'desc':<35} {'mass':>5} {'dv':>5} {'tof_d':>5} {'time':>5}")
    for idE, idL, desc in test_cases:
        t_start = time.time()
        best = probe_pair(udp, idE, idL)
        dt = time.time() - t_start
        if best:
            m, row, dv, tofd = best
            print(f"  ({idE:>3},{idL:>3}) {desc:<35} {m:>5.0f} {dv:>5.0f} {tofd:>5.1f} {dt:>5.0f}s")
        else:
            print(f"  ({idE:>3},{idL:>3}) {desc:<35}  FAIL              {dt:>5.0f}s")
