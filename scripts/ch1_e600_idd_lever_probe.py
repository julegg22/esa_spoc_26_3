"""E-600 — Ch1 trajectory: is the idD (destination) assignment a live lever?

The official fitness banks, per transfer, min(rocket_mass, (200-DT)*cld) under
a 3-D (idE,idL,idD) matching (each index used once). Our pipeline optimizes
per-pair dv (rocket_mass) and treats idD as secondary. This probe HOLDS the
banked e->m trajectories (and their rocket_mass_i, DT_i) FIXED and re-optimizes
ONLY the destination assignment idD via a linear assignment that maximizes
  sum_i min(rocket_mass_i, (200-DT_i) * cld(m_i, d)).
If the optimum >> current bank, the idD lever is open and the "trajectory
exhausted" verdict measured the wrong objective.

Pure arithmetic on the bank vector + LTL table — NO trajectory propagation,
NO bank write. Diagnostic only.
"""
import json
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = "/home/julian/Projects/esa_spoc_26_3"
D = f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics"
BANK = f"{ROOT}/solutions/upload/trajectory.json"

L = 3.84405000e8
T = 3.7567696752e5
V = L / T
G0 = 9.80665
SEC2DAY = 1.0 / 86400.0

# LTL weights cld[(idl, idd)]
ltl = np.loadtxt(f"{D}/LTL.txt", skiprows=1)
NL = int(ltl[:, 0].max()) + 1
ND = int(ltl[:, 1].max()) + 1
CLD = np.zeros((NL, ND))
for a, b, w in ltl:
    CLD[int(a), int(b)] = w
print(f"[E-600] LTL grid {NL}x{ND}, cld in [{CLD.min():.3f},{CLD.max():.3f}]")

bank = json.load(open(BANK))[0]["decisionVector"]
rows = np.array(bank).reshape(-1, 21)
filled = rows[rows[:, 0] >= 0]
print(f"[E-600] bank rows={len(rows)} filled transfers={len(filled)}")

# per-transfer: idE, idL, idD(current), DV(m/s), DT(days), rocket_mass
idE = filled[:, 0].astype(int)
idL = filled[:, 1].astype(int)
idD_cur = filled[:, 2].astype(int)
DVs = filled[:, 10:19].reshape(-1, 3, 3)   # [n,3 impulses,3 comp]
dv_tot = np.sum(np.linalg.norm(DVs, axis=2), axis=1) * V   # m/s
Ts = filled[:, 19:21]
DT = np.sum(Ts, axis=1) * T * SEC2DAY                      # days
rocket_mass = np.exp(-dv_tot / 311.0 / G0) * 5000.0 - 500.0

# current banked value (replicate fitness arithmetic, current idD)
cap_cur = (200.0 - DT) * CLD[idL, idD_cur]
banked_cur = np.minimum(rocket_mass, cap_cur)
print(f"[E-600] reconstructed bank total = {banked_cur.sum():,.1f} kg "
      f"(official E-049 = 236,420.5)")

# how many transfers are capacity-bound vs dv-bound RIGHT NOW
cap_bound = cap_cur < rocket_mass
print(f"[E-600] capacity-bound transfers (cap<rocket_mass): "
      f"{cap_bound.sum()}/{len(filled)}  "
      f"=> dv-optimizing those adds ZERO banked mass")
print(f"[E-600] sum rocket_mass (uncapped) = {rocket_mass.sum():,.1f} kg; "
      f"mass lost to caps = {(rocket_mass - banked_cur).sum():,.1f} kg")
print(f"[E-600] DT days: min {DT.min():.2f} med {np.median(DT):.2f} "
      f"max {DT.max():.2f}")
print(f"[E-600] current idD cld: min {CLD[idL,idD_cur].min():.3f} "
      f"med {np.median(CLD[idL,idD_cur]):.3f} max {CLD[idL,idD_cur].max():.3f}")

# ---- re-optimize ONLY idD (destinations), trajectories fixed ----
# value[i,d] = min(rocket_mass_i, (200-DT_i)*cld(idL_i, d))
caps = np.outer(200.0 - DT, np.ones(ND)) * CLD[idL, :]   # [n, ND]
value = np.minimum(rocket_mass[:, None], caps)            # [n, ND]
ri, cj = linear_sum_assignment(value, maximize=True)
opt_total = value[ri, cj].sum()
print(f"\n[E-600] === idD-only re-assignment (trajectories FIXED) ===")
print(f"[E-600] optimal idD total = {opt_total:,.1f} kg  "
      f"(delta vs current = {opt_total - banked_cur.sum():+,.1f} kg)")
n_changed = int((cj != idD_cur).sum())
print(f"[E-600] destinations changed: {n_changed}/{len(filled)}")

# also: ceiling if every transfer banked its full rocket_mass (caps non-binding)
print(f"[E-600] uncapped ceiling (Σ rocket_mass) = {rocket_mass.sum():,.1f} kg "
      f"— upper bound for any idD assignment with these trajectories")
