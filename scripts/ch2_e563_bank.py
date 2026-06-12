"""Guard-bank the E-563 medium candidate into solutions/upload/medium.json.

Independently re-scores the candidate with the OFFICIAL kt.fitness, and
commits ONLY if it is feasible (all viols 0, full coverage) AND strictly
better than the current bank, after a backup, with a round-trip re-read
check. Never submits.

Run: PYTHONPATH=src OMP_NUM_THREADS=1 micromamba run -n spoc26 \
        python scripts/ch2_e563_bank.py
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import shutil

import numpy as np

from esa_spoc_26.ch2_kttsp import KTTSP

CAND = "/tmp/ch2_medium_epoch_candidate.json"
BANK = "solutions/upload/medium.json"
INST = glob.glob("reference/SpOC4/*Keplerian*/problems/medium.kttsp")[0]
EPS = 1e-6


def score(kt, dv):
    f = kt.fitness(dv)
    return float(f[0]), bool(kt.is_feasible(f)), [float(x) for x in f[1:]]


def main():
    kt = KTTSP(INST)

    cand_dv = json.load(open(CAND))[0]["decisionVector"]
    bank_dv = json.load(open(BANK))[0]["decisionVector"]

    c_mk, c_feas, c_v = score(kt, cand_dv)
    b_mk, b_feas, b_v = score(kt, bank_dv)
    print(f"candidate: mk={c_mk:.4f} feasible={c_feas} viols={c_v}")
    print(f"bank:      mk={b_mk:.4f} feasible={b_feas} viols={b_v}")

    if not c_feas:
        print("=== ABORT: candidate INFEASIBLE ==="); return
    if not (c_mk < b_mk - EPS):
        print(f"=== NO IMPROVEMENT (cand {c_mk:.4f} >= bank {b_mk:.4f}) ==="); return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("/tmp/bank_bak", exist_ok=True)
    shutil.copy(BANK, f"/tmp/bank_bak/medium_{ts}.json")
    shutil.copy(BANK, f"{BANK}.bak.e563")

    tmp = "/tmp/_e563_bankstep.json"
    json.dump([{"decisionVector": [float(x) for x in cand_dv],
                "problem": "medium",
                "challenge": "spoc-4-keplerian-tomato-traveling-salesperson"}],
              open(tmp, "w"))
    # round-trip BEFORE overwriting the bank
    rt_dv = json.load(open(tmp))[0]["decisionVector"]
    rt_mk, rt_feas, rt_v = score(kt, rt_dv)
    if not (rt_feas and abs(rt_mk - c_mk) < EPS):
        print(f"=== ABORT: round-trip mismatch (rt {rt_mk:.4f} feas {rt_feas}) ==="); return

    shutil.copy(tmp, BANK)
    # final re-read from the actual bank path
    fin_dv = json.load(open(BANK))[0]["decisionVector"]
    f_mk, f_feas, f_v = score(kt, fin_dv)
    print(f"=== BANKED medium {b_mk:.4f} -> {f_mk:.4f} d (-{b_mk - f_mk:.4f}); "
          f"feasible={f_feas} viols={f_v}; backup .bak.e563 + /tmp/bank_bak/medium_{ts}.json ===")


if __name__ == "__main__":
    main()
