"""Ch1 Luna Tomato Logistics — advanced (trajectory-matching) foundation.

Per O-003 / the challenge README: design ≤3-impulse Earth-orbit→Moon-orbit
transfers in the **bicircular problem** (Simó et al. 1995, Earth+Moon+Sun),
then a 3-D assignment (each e/l/d once) maximising discounted delivered
mass within 200 days. The assignment half reuses the validated
`ch1_matching` MIP-LNS on the discounted-mass matrix; this module is the
per-(e,l) transfer-cost build (H-002, baseline-first 2-impulse + refine).

NO server-side validator code is provided for Ch1, so our propagation
must reproduce the competition's Simó BCP. The exact non-dimensional
synodic EOM used here (documented for checkability — to be validated):

    θ(t)  = ω_s · t                      (Sun phase; t0 enters via θ0)
    xs,ys = ρ_s cosθ, ρ_s sinθ           (Sun position, z_s = 0)
    r1² = (x+μ)²+y²+z²    (→ Earth at (−μ,0,0))
    r2² = (x−1+μ)²+y²+z²  (→ Moon  at (1−μ,0,0))
    rs² = (x−xs)²+(y−ys)²+z²
    ẍ = 2ẏ + x − (1−μ)(x+μ)/r1³ − μ(x−1+μ)/r2³ − μs(x−xs)/rs³ − (μs/ρ_s³)xs
    ÿ = −2ẋ + y − (1−μ)y/r1³   − μ y/r2³        − μs(y−ys)/rs³ − (μs/ρ_s³)ys
    z̈ =        − (1−μ)z/r1³   − μ z/r2³        − μs z/rs³

Parameters (challenge README): μ, μs, ρ_s, ω_s; unit scales L, T.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# --- BCP constants (challenge README) ---
MU = 0.01215058439470971
MU_S = 3.3294604877306713e5
RHO_S = 3.88811143e2
OMEGA_S = -9.25195985e-01
L_SI = 3.84405000e8       # m
T_SI = 3.7567696752e5     # s
V_SI = L_SI / T_SI        # m/s
DAY_S = 86400.0
HORIZON_DAYS = 200.0
TU_PER_DAY = DAY_S / T_SI  # synodic time units per day

# --- mass model (Tsiolkovsky + LTL capacity discount) ---
M_WET = 5000.0
M_DRY = 500.0
ISP = 311.0
G0 = 9.80665


def delivered_mass(dv_tot_ms: float, dt_days: float, c_ld: float) -> float:
    """m_l = m_w e^(−ΔV/(Isp g0)) − m_dry ; m_d = min(m_l,(200−ΔT)c_ld)."""
    m_l = M_WET * np.exp(-dv_tot_ms / (ISP * G0)) - M_DRY
    if m_l <= 0.0 or dt_days >= HORIZON_DAYS:
        return 0.0
    return float(min(m_l, (HORIZON_DAYS - dt_days) * c_ld))


# --- data loaders (O-003) ---
def load_orbits(path: str | Path) -> np.ndarray:
    """Rows [id, a(m), e, i(rad)] → array shape (N,4)."""
    return np.loadtxt(path, comments="#")


def load_ltl(path: str | Path, n_l: int = 400, n_d: int = 400) -> np.ndarray:
    """LTL.txt rows `l_id d_id c_ld` → dense (n_l, n_d) capacity matrix."""
    raw = np.loadtxt(path, comments="#")
    c = np.zeros((n_l, n_d))
    c[raw[:, 0].astype(int), raw[:, 1].astype(int)] = raw[:, 2]
    return c


# --- Kepler elements → Cartesian (body-centred, non-dim units) ---
def kepler_to_state(a_nd, e, i, raan, argp, nu, mu_body):
    """Classical elements → (r, v) in the body-centred frame, non-dim.
    a_nd in length units L; mu_body the body's non-dim grav. parameter."""
    p = a_nd * (1.0 - e * e)
    r = p / (1.0 + e * np.cos(nu))
    r_pf = np.array([r * np.cos(nu), r * np.sin(nu), 0.0])
    s = np.sqrt(mu_body / p)
    v_pf = np.array([-s * np.sin(nu), s * (e + np.cos(nu)), 0.0])
    cO, sO = np.cos(raan), np.sin(raan)
    ci, si = np.cos(i), np.sin(i)
    cw, sw = np.cos(argp), np.sin(argp)
    rot = np.array([
        [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
        [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
        [sw * si, cw * si, ci],
    ])
    return rot @ r_pf, rot @ v_pf


def elements_from_state(r, v, mu_body):
    """(r,v) → (a, e, i) in the body-centred frame (validation triple)."""
    rn = np.linalg.norm(r)
    vn = np.linalg.norm(v)
    energy = 0.5 * vn * vn - mu_body / rn
    a = -mu_body / (2.0 * energy)
    h = np.cross(r, v)
    hn = np.linalg.norm(h)
    e_vec = np.cross(v, h) / mu_body - r / rn
    e = np.linalg.norm(e_vec)
    i = np.arccos(np.clip(h[2] / hn, -1.0, 1.0))
    return a, e, i


def build_bcp_integrator():
    """heyoka adaptive Taylor integrator for the Simó BCP (see module doc)."""
    import heyoka as hy

    x, y, z, vx, vy, vz = hy.make_vars("x", "y", "z", "vx", "vy", "vz")
    th = OMEGA_S * hy.time
    xs, ys = RHO_S * hy.cos(th), RHO_S * hy.sin(th)
    r1 = ((x + MU) ** 2 + y**2 + z**2) ** 1.5
    r2 = ((x - 1.0 + MU) ** 2 + y**2 + z**2) ** 1.5
    rs = ((x - xs) ** 2 + (y - ys) ** 2 + z**2) ** 1.5
    om1 = 1.0 - MU
    ax = (2.0 * vy + x - om1 * (x + MU) / r1 - MU * (x - 1.0 + MU) / r2
          - MU_S * (x - xs) / rs - MU_S * xs / RHO_S**3)
    ay = (-2.0 * vx + y - om1 * y / r1 - MU * y / r2
          - MU_S * (y - ys) / rs - MU_S * ys / RHO_S**3)
    az = -om1 * z / r1 - MU * z / r2 - MU_S * z / rs
    return hy.taylor_adaptive(
        [(x, vx), (y, vy), (z, vz), (vx, ax), (vy, ay), (vz, az)],
        [0.0] * 6,
    )


if __name__ == "__main__":  # smoke: integrator builds & runs, energy sane
    ta = build_bcp_integrator()
    eo = load_orbits(
        "reference/SpOC4/Challenge 1 Luna Tomato Logistics/Earth_orbits.txt"
    )
    mo = load_orbits(
        "reference/SpOC4/Challenge 1 Luna Tomato Logistics/Moon_orbits.txt"
    )
    c = load_ltl("reference/SpOC4/Challenge 1 Luna Tomato Logistics/LTL.txt")
    print(f"orbits: E={eo.shape} M={mo.shape}  LTL={c.shape} "
          f"cap[min,med,max]={c[c>0].min():.2f},{np.median(c[c>0]):.2f},"
          f"{c.max():.2f}")
    # spacecraft on Earth orbit 0, near Earth at (−μ,0,0)
    a0 = eo[0, 1] / L_SI
    r, v = kepler_to_state(a0, eo[0, 2], eo[0, 3], 0, 0, 0.0, 1.0 - MU)
    r = r + np.array([-MU, 0, 0])
    ta.state[:] = [*r, *v]
    ta.time = 0.0
    ta.propagate_until(0.05)
    print("propagated 0.05 TU; state finite:", np.all(np.isfinite(ta.state)))
    print("delivered_mass(800 m/s, 30 d, c=10) =",
          round(delivered_mass(800.0, 30.0, 10.0), 3))
