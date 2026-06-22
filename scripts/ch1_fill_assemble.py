"""E-701 FILL assemble + guard-bank. Place each solved empty-slot row (mass>0) into an empty slot
(idE<0) of the bank decision vector, whole-fleet validate via official udp.fitness, guard-bank only if
strictly better AND feasible. Uniqueness holds (rows use unused-pool idE/idL/idD). NEVER submit."""
import sys, json, glob, shutil
import numpy as np
sys.path.insert(0, "/home/julian/Projects/esa_spoc_26_3/src")
from esa_spoc_26.ch1_trajectory import LtlTrajectory
ROOT = "/home/julian/Projects/esa_spoc_26_3"
BANKF = f"{ROOT}/solutions/upload/trajectory.json"

udp = LtlTrajectory(f"{ROOT}/reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
bank_obj = json.load(open(BANKF))
dv = list(bank_obj[0]["decisionVector"]); n = len(dv) // 21
f_bank = udp.fitness(dv); bank_mass = -f_bank[0]
print(f"[FILL-ASM] bank mass={bank_mass:.1f} kg feasible={f_bank[0]<0}; constraints={f_bank[1:]}", flush=True)

empty_idx = [i for i in range(n) if dv[i * 21] < 0]
print(f"[FILL-ASM] {len(empty_idx)} empty slots", flush=True)

solved = []
for fp in glob.glob(f"{ROOT}/cache/ch1_fill_w*of*.json"):
    for rec in json.load(open(fp)):
        if rec.get("mass", 0) > 0 and "row" in rec:
            solved.append(rec)
# guard against duplicate idE/idL across shards (shouldn't happen — disjoint shards)
seen = set(); uniq = []
for r in sorted(solved, key=lambda r: -r["mass"]):
    k = (r["idE"], r["idL"], r["idD"])
    if k in seen:
        continue
    seen.add(k); uniq.append(r)
print(f"[FILL-ASM] {len(uniq)} solved fills (Σ recorded mass {sum(r['mass'] for r in uniq):.0f} kg)", flush=True)

new_dv = list(dv); used = 0
for slot, rec in zip(empty_idx, uniq):
    row = rec["row"]; assert len(row) == 21
    new_dv[slot * 21:(slot + 1) * 21] = [float(v) for v in row]; used += 1
print(f"[FILL-ASM] placed {used} fills into empty slots", flush=True)

f_new = udp.fitness(new_dv); new_mass = -f_new[0]
print(f"[FILL-ASM] NEW mass={new_mass:.1f} kg feasible={f_new[0]<0}; constraints={f_new[1:]}", flush=True)
if f_new[0] >= 0:
    print("[FILL-ASM] ABORT: new fleet INFEASIBLE. No bank change.", flush=True); sys.exit(1)
gain = new_mass - bank_mass
print(f"[FILL-ASM] realized fill gain = {gain:+.1f} kg ({bank_mass:.0f} -> {new_mass:.0f})", flush=True)
if new_mass > bank_mass + 1.0:
    shutil.copy(BANKF, BANKF + ".bak")
    out = [{"decisionVector": [float(v) for v in new_dv]}]
    if "challenge" in bank_obj[0]:
        out[0]["challenge"] = bank_obj[0]["challenge"]
    json.dump(out, open(BANKF, "w"))
    rt = udp.fitness(json.load(open(BANKF))[0]["decisionVector"])
    print(f"[FILL-ASM] GUARD-BANKED. round-trip mass={-rt[0]:.1f} feasible={rt[0]<0} (.bak written)", flush=True)
else:
    print("[FILL-ASM] not strictly better; NO bank change.", flush=True)
