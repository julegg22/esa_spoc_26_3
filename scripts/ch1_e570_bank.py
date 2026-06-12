"""Guard-bank E-570 WSB full-precision rows into solutions/upload/trajectory.json.

For each row json (from ch1_e570_wsb_pair.py), swap the matching (idE,idL)
transfer, official-fitness re-score the FULL solution, and commit ONLY if the
result is valid AND strictly better AND idE/idL/idD remain unique among active
transfers, with a round-trip re-read check. One prebatch backup is written.
Never submits.

Run: PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
        python scripts/ch1_e570_bank.py runs/ch1/e570_row_A_B.json [...]
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import sys

import numpy as np

from esa_spoc_26.ch1_trajectory import LtlTrajectory

P = "solutions/upload/trajectory.json"


def main():
    udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
    os.makedirs("/tmp/bank_bak", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy(P, f"/tmp/bank_bak/trajectory_{ts}_prebatch.json")

    banked, total = 0, 0.0
    for fp in sys.argv[1:]:
        j = json.load(open(fp))
        rowf = [float(x) for x in j["row"]]
        idE, idL, idD = j["idE"], j["idL"], int(rowf[2])
        d = json.load(open(P))
        dv = np.array(d[0]["decisionVector"]).reshape(-1, 21)
        idx = [i for i, r in enumerate(dv)
               if int(r[0]) == idE and int(r[1]) == idL]
        if len(idx) != 1:
            print(f"({idE},{idL}) SKIP: {len(idx)} matching rows")
            continue
        i = idx[0]
        before = udp.fitness(dv.flatten())[0]
        dv2 = dv.copy()
        dv2[i] = rowf
        after = udp.fitness(dv2.flatten())[0]
        act = [(int(r[0]), int(r[1]), int(r[2])) for r in dv2 if int(r[0]) >= 0]
        uniq = all(len([t for t in act if t[c] == v]) == 1
                   for c, v in [(0, idE), (1, idL), (2, idD)])
        if not (after < 0 and abs(after) > abs(before) + 1e-6 and uniq):
            print(f"({idE},{idL}) NOT banked (after={after:.1f} uniq={uniq})")
            continue
        tmp = "/tmp/_e570_bankstep.json"
        json.dump([{"decisionVector": dv2.flatten().tolist()}], open(tmp, "w"))
        rs = udp.fitness(
            np.array(json.load(open(tmp))[0]["decisionVector"]).flatten())[0]
        if abs(rs - after) >= 1e-6:
            print(f"({idE},{idL}) round-trip mismatch, skip")
            continue
        shutil.copy(tmp, P)
        g = -after - (-before)
        total += g
        banked += 1
        print(f"({idE},{idL}) BANKED +{g:.1f} -> {-after:.1f} kg")

    final = udp.fitness(
        np.array(json.load(open(P))[0]["decisionVector"]).flatten())[0]
    print(f"--- {banked}/{len(sys.argv)-1} banked, +{total:.1f} kg; "
          f"Ch1 trajectory now {-final:.1f} kg ---")


if __name__ == "__main__":
    main()
