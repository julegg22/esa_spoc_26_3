"""E-701 fleet ASSEMBLE + guard-bank. Swap each improved pair's row (gain>0) into the bank decision
vector (keeping idD ⇒ assignment/uniqueness preserved), whole-fleet validate via official udp.fitness,
and guard-bank only if strictly better AND feasible. NEVER submit."""
import sys, json, glob, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANKF = f"{ROOT}/solutions/upload/trajectory.json"

udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
bank_obj = json.load(open(BANKF))
dv = list(bank_obj[0]["decisionVector"])
n_rows = len(dv) // 21

# bank baseline
f_bank = udp.fitness(dv)
bank_mass = -f_bank[0] if f_bank[0] < 0 else None
print(f"[ASSEMBLE] bank fitness[0]={f_bank[0]:.3f} -> mass={bank_mass:.1f} kg; constraints={f_bank[1:]}", flush=True)

# collect improved rows keyed by (idE,idL)
improved = {}
for fp in glob.glob(f"{ROOT}/cache/ch1_ecc_fleet_w*of3.json"):
    for rec in json.load(open(fp)):
        if rec.get("gain", 0) > 0 and "row" in rec:
            improved[(rec["idE"], rec["idL"])] = rec
print(f"[ASSEMBLE] {len(improved)} improved pairs from checkpoints; Σ recorded gain = "
      f"{sum(r['gain'] for r in improved.values()):.0f} kg", flush=True)

# swap rows
swapped = 0
new_dv = list(dv)
for i in range(n_rows):
    r0 = dv[i * 21]
    if r0 < 0:
        continue
    idE, idL = int(dv[i * 21]), int(dv[i * 21 + 1])
    rec = improved.get((idE, idL))
    if rec is None:
        continue
    row = rec["row"]
    assert len(row) == 21 and int(row[0]) == idE and int(row[1]) == idL and int(row[2]) == int(dv[i * 21 + 2]), \
        f"row mismatch at {i}: {row[:3]} vs bank {dv[i*21:i*21+3]}"
    new_dv[i * 21:(i + 1) * 21] = [float(v) for v in row]
    swapped += 1
print(f"[ASSEMBLE] swapped {swapped} rows into the fleet", flush=True)

# whole-fleet validation
f_new = udp.fitness(new_dv)
new_mass = -f_new[0] if f_new[0] < 0 else None
feasible = f_new[0] < 0  # official: feasible solutions score negative (mass)
print(f"[ASSEMBLE] NEW fitness[0]={f_new[0]:.3f} -> mass={new_mass:.1f} kg; constraints={f_new[1:]}", flush=True)
if new_mass is None:
    print("[ASSEMBLE] ABORT: new fleet INFEASIBLE (fitness>=0). No bank change.", flush=True)
    sys.exit(1)
gain = new_mass - bank_mass
print(f"[ASSEMBLE] realized gain = {gain:+.1f} kg  (bank {bank_mass:.0f} -> {new_mass:.0f})", flush=True)

if new_mass > bank_mass + 1.0:
    shutil.copy(BANKF, BANKF + ".bak")
    out = [{"decisionVector": [float(v) for v in new_dv]}]
    if "challenge" in bank_obj[0]:
        out[0]["challenge"] = bank_obj[0]["challenge"]
    json.dump(out, open(BANKF, "w"))
    # round-trip verify
    rt = udp.fitness(json.load(open(BANKF))[0]["decisionVector"])
    print(f"[ASSEMBLE] GUARD-BANKED. round-trip mass={-rt[0]:.1f} feasible={rt[0]<0} (backup .bak written)", flush=True)
    print(f"[ASSEMBLE] BANK UPDATED: trajectory {bank_mass:.0f} -> {new_mass:.0f} kg (+{gain:.0f})", flush=True)
else:
    print("[ASSEMBLE] new fleet not strictly better; NO bank change.", flush=True)
