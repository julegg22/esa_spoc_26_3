import sys, numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, earth_orbit_state, propagate, T, V, L
from esa_spoc_26.ch1_traj_lambert_dc import best_lambert_seed, inertial_to_synodic_pos
from esa_spoc_26.ch1_trajectory_solve import solve_arrival_dv
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
for e, l in [(241, 50), (249, 22)]:
    aM, eM, iM = udp.moon_data[l]
    seed = best_lambert_seed(udp, e, l)
    aE, eE, iE = udp.earth_data[e]
    tof_nd = seed["tof_d"] * 86400 / T
    pv0 = earth_orbit_state(aE, eE, iE, seed["raan_e"], seed["argp_e"], seed["ea_e"])
    r_arr_syn = np.array(inertial_to_synodic_pos(seed["r_arr"], tof_nd))
    dv0_seed = np.asarray(seed["dv1"]) / V
    print(f"\n##### ({e},{l}) tof={seed['tof_d']}d seed_dv={seed['total']:.0f} | aM={aM:.3e} eM={eM:.3f} | r_arr|={np.linalg.norm(r_arr_syn)*L:.3e}", flush=True)
    for split in (0.3, 0.5, 0.7):
        t1, t2 = tof_nd * split, tof_nd * (1 - split)
        def resid(x):
            pv1 = propagate(pv0, 0.0, [x[:3].tolist(), x[3:6].tolist(), [0, 0, 0]], [t1, t2])
            if len(pv1) == 0:
                return np.array([50., 50., 50.])
            return np.array(pv1[0]) - r_arr_syn
        sol = least_squares(resid, np.concatenate([dv0_seed, np.zeros(3)]), method="trf", xtol=1e-12, max_nfev=300)
        pv1 = propagate(pv0, 0.0, [sol.x[:3].tolist(), sol.x[3:6].tolist(), [0, 0, 0]], [t1, t2])
        if len(pv1) == 0:
            print(f"  split {split}: propagate EMPTY (impact)", flush=True); continue
        endpos_err_km = np.linalg.norm(np.array(pv1[0]) - r_arr_syn) * L / 1000
        # radius from Moon at endpoint
        from esa_spoc_26.ch1_trajectory import CR3BP_MU_EARTH_MOON
        r_from_moon = np.linalg.norm([pv1[0][0] - 1 + CR3BP_MU_EARTH_MOON, pv1[0][1], pv1[0][2]]) * L
        a2 = solve_arrival_dv(pv1, aM, eM, iM)
        win = f"[{aM*(1-eM):.3e},{aM*(1+eM):.3e}]"
        print(f"  split {split}: LSQ cost={sol.cost:.2e} endpos_err={endpos_err_km:.0f}km | r_from_moon={r_from_moon:.3e} window={win} arrival={'OK' if a2 else 'None'}", flush=True)
