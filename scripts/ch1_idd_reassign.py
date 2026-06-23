"""E-706 — Ch1 trajectory: optimal idd (destination) re-assignment. The objective is
min(mass, (200-dt)*cld) with cld=ltl_dict[(idl,idd)]; idd does NOT affect the trajectory (UDP validates
only idE/idL), so it's a cleanly-separable assignment. 65/400 transfers are cap-bound (losing 16,786 kg)
because their destination gives a low cld. Hungarian on v[i,j]=min(mass_i,(200-dt_i)*cld[idl_i,j])
recovers it with ZERO trajectory change. Guard-bank if officially valid + strictly better."""
import sys, json, shutil
import numpy as np
import pykep as pk
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, T as TUNIT
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANKF = f"{ROOT}/solutions/upload/trajectory.json"

udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
ltl = udp.ltl_dict; nL = udp.moon_data.shape[0]; nD = 400
CLD = np.zeros((nL, nD))
for (a, b), w in ltl.items():
    if a < nL and b < nD:
        CLD[int(a), int(b)] = w
bo = json.load(open(BANKF)); dv = list(bo[0]["decisionVector"]); n = len(dv) // 21
f0 = udp.fitness(dv); bank_mass = -f0[0]
print(f"[E-706] bank {bank_mass:.0f} kg feasible={f0[0]<0}")

# per filled transfer: row index, mass, dt, idl
idx = []; masses = []; dts = []; idls = []
for i in range(n):
    r = dv[i * 21:i * 21 + 21]
    if r[0] < 0:
        continue
    DV = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
    dt = (r[19] + r[20]) * TUNIT * pk.SEC2DAY
    idx.append(i); masses.append(np.exp(-DV / 311. / pk.G0) * 5000 - 500.); dts.append(dt); idls.append(int(r[1]))
masses = np.array(masses); dts = np.array(dts); idls = np.array(idls)
cap = (200 - dts)[:, None] * CLD[idls, :]
Vm = np.minimum(masses[:, None], cap)
ri, ci = linear_sum_assignment(-Vm)
print(f"[E-706] Hungarian optimal idd: predicted score {Vm[ri, ci].sum():.0f}")

# write re-assigned idd into the decision vector (idd is column index 2 of each row)
new_dv = list(dv)
for k, row_i in enumerate(idx):
    new_dv[row_i * 21 + 2] = float(ci[k])
fn = udp.fitness(new_dv); new_mass = -fn[0]
print(f"[E-706] OFFICIAL re-scored: {new_mass:.0f} kg feasible={fn[0]<0} gain {new_mass-bank_mass:+.0f}")
if fn[0] < 0 and new_mass > bank_mass + 1.0:
    shutil.copy(BANKF, BANKF + ".bak3")
    out = [{"decisionVector": [float(v) for v in new_dv]}]
    if "challenge" in bo[0]:
        out[0]["challenge"] = bo[0]["challenge"]
    json.dump(out, open(BANKF, "w"))
    rt = udp.fitness(json.load(open(BANKF))[0]["decisionVector"])
    print(f"[E-706] GUARD-BANKED {bank_mass:.0f} -> {new_mass:.0f} kg (round-trip {-rt[0]:.0f}, feasible={rt[0]<0}, .bak3 saved)")
else:
    print("[E-706] not better or infeasible; no bank change")
