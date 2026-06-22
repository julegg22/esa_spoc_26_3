"""E-701 step 1: validate heyoka variational STM extraction vs finite-difference, for the BCP arc.
The STM (analytic d(final_state)/d(initial_state)) is the tool that lets a Newton corrector close the
384m/1e-6 official window where finite-diff DCs stall at ~1km on sensitive 3-body arcs."""
import sys, numpy as np
sys.path.insert(0, "src")
import heyoka as hy
from esa_spoc_26.ch1_trajectory import bcp_dyn, CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S, L, T

PARS = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S, BCP_OMEGA_S]
sys0 = bcp_dyn()

# --- variational integrator (1st order, w.r.t. state vars) ---
vsys = hy.var_ode_sys(sys0, hy.var_args.vars, order=1)
ta_v = hy.taylor_adaptive(vsys, [0.0] * 6, tol=1e-16, compact_mode=True)
ta_v.pars[:] = PARS
print("variational state length:", len(ta_v.state), "(expect 6 + 36 = 42)")

# --- plain integrator for finite-diff ---
ta_p = hy.taylor_adaptive(sys0, [0.0] * 6, tol=1e-16)
ta_p.pars[:] = PARS


def prop_plain(s0, t0, tof):
    ta_p.time = t0; ta_p.state[:] = s0; ta_p.propagate_for(tof)
    return np.array(ta_p.state[:6])


def prop_stm(s0, t0, tof):
    ta_v.time = t0
    ta_v.state[:6] = s0
    # set variational ICs to identity (d x_i(0)/d x_j(0) = delta_ij), laid out row-major after the 6 states
    ta_v.state[6:] = np.eye(6).flatten()
    ta_v.propagate_for(tof)
    final = np.array(ta_v.state[:6])
    stm = np.array(ta_v.state[6:42]).reshape(6, 6)
    return final, stm


# a representative Earth->Moon-ish arc state (synodic nondim) and a 5-day tof
s0 = np.array([0.02, 0.01, 0.005, 0.6, 0.9, 0.1])
t0 = 0.3
tof = 5.0 * 86400 / T

f_plain = prop_plain(s0, t0, tof)
f_stm, STM = prop_stm(s0, t0, tof)
print("final state match (plain vs var):", np.linalg.norm(f_plain - f_stm))

# finite-diff STM
eps = 1e-7
fd = np.zeros((6, 6))
for j in range(6):
    sp = s0.copy(); sp[j] += eps
    fd[:, j] = (prop_plain(sp, t0, tof) - f_plain) / eps
err = np.abs(STM - fd)
print(f"STM vs finite-diff: max abs err {err.max():.3e}, max rel {(err/(np.abs(fd)+1e-9)).max():.3e}")
print("STM[:3,:3] (analytic):\n", np.array2string(STM[:3, :3], precision=3))
print("-> STM VALID" if err.max() < 1e-3 * max(1, np.abs(STM).max()) else "-> STM MISMATCH (check layout)")
