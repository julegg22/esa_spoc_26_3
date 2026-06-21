"""AUDIT (user: 'always consider experiments may have errors'): clean decomposition of the
EXPENSIVE vs CHEAP circular captures from the bank's OWN data. Where is the expense actually —
dv0 (apogee, floored), dv1 (mid-burn), or dv2 (capture)? My '3670 floor' claim contradicts the
bank's cheapest circular capture (1955), so the decomposition was muddled. Ground-truth it."""
import json, math, numpy as np, sys
sys.path.insert(0, "src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
L = 3.84405e8; V = L / 3.7567696752e5
Ea, Ee = udp.earth_data[:, 0], udp.earth_data[:, 1]; Eapo = Ea * (1 + Ee)
eL = udp.moon_data[:, 1]; aL = udp.moon_data[:, 0]
bank = json.load(open("solutions/upload/trajectory.json"))[0]["decisionVector"]
P = []
for i in range(0, len(bank), 21):
    if bank[i] < 0:
        continue
    r = bank[i:i + 21]; e, l = int(r[0]), int(r[1])
    dv0 = np.linalg.norm(r[10:13]) * V; dv1 = np.linalg.norm(r[13:16]) * V; dv2 = np.linalg.norm(r[16:19]) * V
    P.append((e, l, dv0, dv1, dv2, dv0 + dv1 + dv2, Eapo[e] / L, eL[l]))
P = np.array(P)
circ = P[P[:, 7] < 0.1]
print(f"CIRCULAR captures (n={len(circ)}): total dv min {circ[:,5].min():.0f} median {np.median(circ[:,5]):.0f} max {circ[:,5].max():.0f}")
print()
print("    cohort        n   dv0    dv1    dv2   total  apogee/L")
for name, mask in [("cheapest (tot<2500)", circ[:, 5] < 2500),
                   ("median (4000-5000)", (circ[:, 5] >= 4000) & (circ[:, 5] < 5000)),
                   ("expensive (>5500)", circ[:, 5] > 5500)]:
    c = circ[mask]
    if len(c):
        print(f"  {name:18} {len(c):3d}  {np.median(c[:,2]):5.0f}  {np.median(c[:,3]):5.0f}  {np.median(c[:,4]):5.0f}  {np.median(c[:,5]):6.0f}  {np.median(c[:,6]):.3f}")
print()
print("=> compare dv0 (apogee-set), dv1 (mid-burn, reducible?), dv2 (capture).")
print("   If expensive cohort's dv0 is HIGH (low apogee) -> expense is DEPARTURE (floored, NOT reducible).")
print("   If expensive cohort's dv1/dv2 are HIGH vs cheap -> expense is mid-burn/capture (REDUCIBLE).")
# the cheapest circular capture: what makes it cheap?
cmin = circ[np.argmin(circ[:, 5])]
print(f"\ncheapest circular pair (e={int(cmin[0])},l={int(cmin[1])}): dv0={cmin[2]:.0f} dv1={cmin[3]:.0f} dv2={cmin[4]:.0f} tot={cmin[5]:.0f} apogee/L={cmin[6]:.3f} eL={cmin[7]:.3f}")
cmax = circ[np.argmax(circ[:, 5])]
print(f"dearest  circular pair (e={int(cmax[0])},l={int(cmax[1])}): dv0={cmax[2]:.0f} dv1={cmax[3]:.0f} dv2={cmax[4]:.0f} tot={cmax[5]:.0f} apogee/L={cmax[6]:.3f} eL={cmax[7]:.3f}")
# the apogee->dv0 floor check: is dv0 ~ the Hohmann apogee-raise?
import math as m
muE = 398600435507000.0
def hohmann_dv0(apo_m):
    rp = apo_m  # treat near-circular Earth orbit at radius=apogee
    rM = L
    at = (rp + rM) / 2
    vp_circ = m.sqrt(muE / rp)
    vp_tr = m.sqrt(muE * (2 / rp - 1 / at))
    return vp_tr - vp_circ
for apoL in [0.02, 0.05, 0.11]:
    print(f"  Hohmann dv0 floor for apogee/L={apoL}: {hohmann_dv0(apoL*L):.0f} m/s")
