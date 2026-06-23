"""E-708 assemble: swap the improved extended-tof rows into the bank, THEN re-optimize idd (the larger
dt shifts the cap), guard-bank if the final officially beats 347,648. NEVER submit."""
import sys, json, glob, shutil
import numpy as np
import pykep as pk
from scipy.optimize import linear_sum_assignment
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory, V, T as TUNIT
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANKF = f"{ROOT}/solutions/upload/trajectory.json"

udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
bo = json.load(open(BANKF)); dv = list(bo[0]["decisionVector"]); n = len(dv) // 21
f0 = udp.fitness(dv); bank_mass = -f0[0]
print(f"[E-708-ASM] bank {bank_mass:.0f} kg feasible={f0[0]<0}")

# improved extended-tof rows keyed by (idE,idL)
better = {}
for f in glob.glob(f"{ROOT}/cache/ch1_longtof_w*of3.json"):
    for rec in json.load(open(f)):
        if rec.get("better") and "row" in rec:
            better[(rec["e"], rec["l"])] = rec["row"]
print(f"[E-708-ASM] {len(better)} improved extended-tof rows")

new_dv = list(dv); swapped = 0
for i in range(n):
    r = dv[i * 21:i * 21 + 21]
    if r[0] < 0:
        continue
    key = (int(r[0]), int(r[1]))
    if key in better:
        row = better[key]
        assert int(row[0]) == key[0] and int(row[1]) == key[1]
        # keep the bank row's idd (idd re-optimized below); row's idd should already match
        new_dv[i * 21:(i + 1) * 21] = [float(v) for v in row]
        swapped += 1
print(f"[E-708-ASM] swapped {swapped} extended-tof rows")

# raw score (idd unchanged) - extended-tof dt may now hit the cap
f_raw = udp.fitness(new_dv); raw_mass = -f_raw[0] if f_raw[0] < 0 else None
print(f"[E-708-ASM] raw (pre-idd-reopt): {raw_mass} feasible={f_raw[0]<0}")

# re-optimize idd on the new dt's
ltl = udp.ltl_dict; nL = udp.moon_data.shape[0]; nD = 400
CLD = np.zeros((nL, nD))
for (a, b), w in ltl.items():
    if a < nL and b < nD:
        CLD[int(a), int(b)] = w
idx = []; masses = []; dts = []; idls = []
for i in range(n):
    r = new_dv[i * 21:i * 21 + 21]
    if r[0] < 0:
        continue
    DV = (np.linalg.norm(r[10:13]) + np.linalg.norm(r[13:16]) + np.linalg.norm(r[16:19])) * V
    dt = (r[19] + r[20]) * TUNIT * pk.SEC2DAY
    idx.append(i); masses.append(np.exp(-DV / 311. / pk.G0) * 5000 - 500.); dts.append(dt); idls.append(int(r[1]))
masses = np.array(masses); dts = np.array(dts); idls = np.array(idls)
Vm = np.minimum(masses[:, None], (200 - dts)[:, None] * CLD[idls, :])
ri, ci = linear_sum_assignment(-Vm)
for k, row_i in enumerate(idx):
    new_dv[row_i * 21 + 2] = float(ci[k])
f_fin = udp.fitness(new_dv); fin_mass = -f_fin[0] if f_fin[0] < 0 else None
print(f"[E-708-ASM] FINAL (extended-tof + idd-reopt): {fin_mass} feasible={f_fin[0]<0} gain {fin_mass-bank_mass:+.0f}" if fin_mass else "[E-708-ASM] INFEASIBLE")

if fin_mass and f_fin[0] < 0 and fin_mass > bank_mass + 1.0:
    shutil.copy(BANKF, BANKF + ".bak4")
    out = [{"decisionVector": [float(v) for v in new_dv]}]
    if "challenge" in bo[0]:
        out[0]["challenge"] = bo[0]["challenge"]
    json.dump(out, open(BANKF, "w"))
    rt = udp.fitness(json.load(open(BANKF))[0]["decisionVector"])
    print(f"[E-708-ASM] GUARD-BANKED {bank_mass:.0f} -> {fin_mass:.0f} kg (round-trip {-rt[0]:.0f}, feasible={rt[0]<0}, .bak4) | rank-5 372,729 dist {372729-fin_mass:+.0f}")
else:
    print("[E-708-ASM] not better; no bank change")
