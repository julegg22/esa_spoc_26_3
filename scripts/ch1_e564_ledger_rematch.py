"""E-564: Ch1 bank-ledger reconciliation + re-matching.

1. Officially evaluate solutions/upload/trajectory.json (exact bank kg).
2. Union per-pair table: bank rows + all runs/ch1/*_results.json caches
   (format "idE,idL" -> [mass, row21, dv]). Keep ranked candidate rows
   per (idE,idL) by m_l recomputed from the row's dv components.
3. Two-stage Hungarian re-matching (stage 1: (idE,idL) with optimistic
   destination cap; stage 2: (transfer,idD) with actual caps), with a
   validation loop: any officially-invalid selected row is dropped from
   the candidate table and the matching is re-solved.
4. Assemble, evaluate with the official fitness, and bank ONLY if
   strictly better than the current bank. Atomic replace + re-validate.

Single-threaded, compute-light. No per-pair trajectory re-solving.
"""
import json
import math
import os
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, '/home/julian/Projects/esa_spoc_26_3/src')

import heyoka as hy
import pykep as pk
from esa_spoc_26.ch1_trajectory import (
    LtlTrajectory, V, T, L, CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S,
    BCP_OMEGA_S, bcp_dyn, state2earth, state2moon)

ROOT = "/home/julian/Projects/esa_spoc_26_3/reference/SpOC4/Challenge 1 Luna Tomato Logistics/"
BANK = Path("/home/julian/Projects/esa_spoc_26_3/solutions/upload/trajectory.json")
RUNS = Path("/home/julian/Projects/esa_spoc_26_3/runs/ch1")
LOG = RUNS / "76_e564_ledger_rematch.log"

M0, M_DRY, ISP = 5000.0, 500.0, 311.0
T_DAYS = pk.SEC2DAY * T

CACHES = [
    "bcp_apogee_expand_results.json",
    "bcp_apogee_expand_v3_results.json",
    "bcp_apogee_expand_v6_results.json",
    "bcp_apogee_expand_v7_results.json",
    "bcp_apogee_expand_v8_results.json",
    "extended_results.json",
    "hungarian_seeded_results.json",
    "phase2_b6fix_results.json",
    "phase_a_v2_results.json",
    "raan_results.json",
    "smart_coverage_results.json",
    "tier1a_v2_results.json",
    "tier1_light_results.json",
    "tier2_heavy_results.json",
    "unused_pool_results.json",
    "e647_fill_results.json",
]

_logf = open(LOG, "a", buffering=1)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    _logf.write(line + "\n")


def m_l_from_row(row):
    dv0 = math.sqrt(row[10] ** 2 + row[11] ** 2 + row[12] ** 2) * V
    dv1 = math.sqrt(row[13] ** 2 + row[14] ** 2 + row[15] ** 2) * V
    dv2 = math.sqrt(row[16] ** 2 + row[17] ** 2 + row[18] ** 2) * V
    return math.exp(-(dv0 + dv1 + dv2) / (ISP * pk.G0)) * M0 - M_DRY


def dt_d_from_row(row):
    return (row[19] + row[20]) * T_DAYS


# ── fast validator: same physics as official propagate(), but reuses one
#    taylor_adaptive instance (the official one rebuilds + recompiles per
#    call). Final numbers always come from udp.fitness().
class FastValidator:
    def __init__(self, udp):
        self.udp = udp
        x, y, z = hy.make_vars("x", "y", "z")
        self.hits = []

        def cb(ta, time_, d_sgn):
            self.hits.append(time_)

        ev_E = hy.nt_event(
            (x + hy.par[0]) ** 2 + y ** 2 + z ** 2
            - (pk.EARTH_RADIUS + 99000) ** 2 / L ** 2, callback=cb)
        ev_M = hy.nt_event(
            (x - 1 + hy.par[0]) ** 2 + y ** 2 + z ** 2
            - (1737400.0 + 30000) ** 2 / L ** 2, callback=cb)
        self.ta = hy.taylor_adaptive(bcp_dyn(), tol=1e-16,
                                     nt_events=[ev_E, ev_M])
        self.ta.pars[:] = [CR3BP_MU_EARTH_MOON, BCP_MU_S, BCP_RHO_S,
                           BCP_OMEGA_S]

    def propagate(self, posvel, t0, DVs, Ts):
        self.hits.clear()
        ta = self.ta
        ta.time = t0
        pv = deepcopy(posvel)
        pv[1][0] += DVs[0][0]
        pv[1][1] += DVs[0][1]
        pv[1][2] += DVs[0][2]
        ta.state[:6] = pv[0] + pv[1]
        for i, tt in enumerate(Ts):
            ta.propagate_for(tt)
            ta.state[3] += DVs[i + 1][0]
            ta.state[4] += DVs[i + 1][1]
            ta.state[5] += DVs[i + 1][2]
        if self.hits:
            return []
        return [list(ta.state[:3]), list(ta.state[3:6])]

    def validate_row(self, row):
        """Mirror of udp._validate_transfer on a 21-float row."""
        idE, idL = int(row[0]), int(row[1])
        t0 = row[3]
        posvel = [[row[4], row[5], row[6]], [row[7], row[8], row[9]]]
        DVs = [[row[10], row[11], row[12]], [row[13], row[14], row[15]],
               [row[16], row[17], row[18]]]
        Ts = [row[19], row[20]]
        udp = self.udp
        aE, eE, iE = udp.earth_data[idE]
        aL, eL, iL = udp.moon_data[idL]
        if not udp._match_orbit(state2earth(deepcopy(posvel)), aE, eE, iE):
            return False
        pv1 = self.propagate(posvel, t0, DVs, Ts)
        if len(pv1) == 0:
            return False
        if not udp._match_orbit(state2moon(pv1), aL, eL, iL):
            return False
        return True


def official_eval(udp, chromosome):
    t = time.time()
    f = udp.fitness(chromosome)[0]
    return -f, time.time() - t


def assemble(udp, rows):
    chrom = []
    for r in rows:
        chrom.extend([float(v) for v in r])
    n_pad = (udp.dim - len(chrom)) // 21
    for _ in range(n_pad):
        chrom.extend([-1.0] + [0.0] * 20)
    return chrom


def main():
    log("=" * 70)
    log("E-564 ledger reconciliation + re-matching start")
    udp = LtlTrajectory(ROOT)
    n_d = max(d for (_, d) in udp.ltl_dict) + 1
    n_l = max(l for (l, _) in udp.ltl_dict) + 1
    log(f"data: earth={udp.earth_data.shape[0]} moon={udp.moon_data.shape[0]} "
        f"ltl_dict={len(udp.ltl_dict)} (n_l={n_l}, n_d={n_d})")

    # ── Task 1: official eval of current bank ────────────────────────────
    bank = json.load(open(BANK))
    bank_dv = bank[0]["decisionVector"]
    bank_rows = [list(bank_dv[i:i + 21]) for i in range(0, len(bank_dv), 21)
                 if bank_dv[i] >= 0]
    log(f"bank: {len(bank_rows)} active transfers; evaluating officially ...")
    bank_mass, dt_eval = official_eval(udp, bank_dv)
    log(f"BANK OFFICIAL = {bank_mass:.2f} kg  ({len(bank_rows)} transfers, "
        f"eval {dt_eval:.0f}s)")

    # ── Task 2: union per-pair table ─────────────────────────────────────
    # cands[(idE,idL)] = list of (m_l, dt_d, row, source) sorted desc by m_l
    cands = {}

    def add(row, source):
        idE, idL = int(row[0]), int(row[1])
        m_l = m_l_from_row(row)
        if m_l <= 0:
            return
        dt_d = dt_d_from_row(row)
        lst = cands.setdefault((idE, idL), [])
        # dedupe identical trajectories
        for m2, _, r2, _ in lst:
            if abs(m2 - m_l) < 1e-9 and r2[19] == row[19] and r2[10] == row[10]:
                return
        lst.append((m_l, dt_d, row, source))
        lst.sort(key=lambda t_: -t_[0])
        del lst[4:]  # keep top-4 fallbacks per pair

    for r in bank_rows:
        add(r, "bank")
    n_after_bank = len(cands)
    log(f"union: bank contributes {n_after_bank} pairs")
    src_stats = {}
    for name in CACHES:
        p = RUNS / name
        if not p.exists():
            continue
        d = json.load(open(p))
        n_new, n_better = 0, 0
        for k, v in d.items():
            idE, idL = map(int, k.split(','))
            row = list(v[1])
            key = (idE, idL)
            old_best = cands[key][0][0] if key in cands else None
            add(row, name)
            if key in cands:
                new_best = cands[key][0][0]
                if old_best is None:
                    n_new += 1
                elif new_best > old_best + 1e-9:
                    n_better += 1
        src_stats[name] = (n_new, n_better)
        log(f"  {name}: {len(d)} entries, +{n_new} new pairs, "
            f"{n_better} improved best -> {len(cands)} pairs total")

    # how many bank rows are beaten by cache rows
    n_stale = 0
    stale_gain = 0.0
    bank_best = {}
    for r in bank_rows:
        bank_best[(int(r[0]), int(r[1]))] = m_l_from_row(r)
    for key, m_bank in bank_best.items():
        m_uni = cands[key][0][0]
        if m_uni > m_bank + 1.0:
            n_stale += 1
            stale_gain += m_uni - m_bank
    log(f"stale bank pairs (union m_l better by >1kg): {n_stale}, "
        f"sum m_l gain {stale_gain:.0f} kg (pre-cap, pre-matching)")

    # ── Task 3+4: matching with validation loop ──────────────────────────
    fv = FastValidator(udp)
    valid_cache = {}   # id(row-tuple) -> bool

    max_cld = np.zeros(n_l)
    for (l, d_), c in udp.ltl_dict.items():
        if c > max_cld[l]:
            max_cld[l] = c

    nE = udp.earth_data.shape[0]
    nL = udp.moon_data.shape[0]

    for it in range(1, 11):
        # stage 1: Hungarian on (idE,idL), optimistic cap
        M = np.zeros((nE, nL))
        for (idE, idL), lst in cands.items():
            m_l, dt_d, _, _ = lst[0]
            M[idE, idL] = min(m_l, max_cld[idL] * max(0.0, 200.0 - dt_d))
        ri, ci = linear_sum_assignment(-M)
        sel = [(r, c) for r, c in zip(ri, ci) if M[r, c] > 0.5]
        opt_sum = sum(M[r, c] for r, c in sel)
        log(f"[iter {it}] stage1: {len(sel)} pairs, optimistic {opt_sum:.0f} kg")

        # stage 2: Hungarian on (transfer, idD), actual caps
        M2 = np.zeros((len(sel), n_d))
        for ti, (idE, idL) in enumerate(sel):
            m_l, dt_d, _, _ = cands[(idE, idL)][0]
            w = max(0.0, 200.0 - dt_d)
            for d_ in range(n_d):
                c = udp.ltl_dict.get((idL, d_))
                if c is not None:
                    M2[ti, d_] = min(m_l, c * w)
        ri2, ci2 = linear_sum_assignment(-M2)
        chosen = [(ti, dd) for ti, dd in zip(ri2, ci2) if M2[ti, dd] > 0.5]
        act_sum = sum(M2[ti, dd] for ti, dd in chosen)
        log(f"[iter {it}] stage2: {len(chosen)} transfers, "
            f"table-predicted {act_sum:.0f} kg")

        # validate selected rows (fast validator, cached)
        n_bad = 0
        final_rows = []
        for ti, dd in chosen:
            idE, idL = sel[ti]
            m_l, dt_d, row, source = cands[(idE, idL)][0]
            key = tuple(row)
            ok = valid_cache.get(key)
            if ok is None:
                ok = fv.validate_row(row)
                valid_cache[key] = ok
            if ok:
                nr = list(row)
                nr[2] = float(dd)
                final_rows.append((nr, source, M2[ti, dd]))
            else:
                n_bad += 1
                lst = cands[(idE, idL)]
                lst.pop(0)
                if not lst:
                    del cands[(idE, idL)]
                log(f"[iter {it}]   INVALID row ({idE},{idL}) m_l={m_l:.0f} "
            f"src={source} -> dropped, {len(cands.get((idE, idL), []))} "
            f"fallbacks left")
        log(f"[iter {it}] validation: {len(final_rows)} ok, {n_bad} invalid")
        if n_bad == 0:
            break

    # per-source breakdown of final selection
    by_src = {}
    for _, source, w in final_rows:
        a = by_src.setdefault(source, [0, 0.0])
        a[0] += 1
        a[1] += w
    log("final selection per-source (count, table kg):")
    for s, (n, kg) in sorted(by_src.items(), key=lambda kv: -kv[1][1]):
        log(f"  {s:40s} {n:4d}  {kg:10.0f}")

    # ── official eval of re-matched chromosome ───────────────────────────
    chrom = assemble(udp, [r for r, _, _ in final_rows])
    table_pred = sum(w for _, _, w in final_rows)
    log(f"assembled {len(final_rows)} transfers; table-predicted "
        f"{table_pred:.0f} kg; official eval ...")
    new_mass, dt_eval = official_eval(udp, chrom)
    log(f"RE-MATCHED OFFICIAL = {new_mass:.2f} kg (eval {dt_eval:.0f}s); "
        f"table predicted {table_pred:.0f} kg "
        f"(delta {new_mass - table_pred:+.1f})")
    if table_pred > 0 and abs(new_mass - table_pred) / table_pred > 0.05:
        log("WARNING: official vs table disagree >5% — investigate before "
            "banking (per task constraint).")

    # ── Task 5: guarded bank ─────────────────────────────────────────────
    if new_mass > bank_mass + 0.5:
        bak = str(BANK) + ".bak.e564"
        Path(bak).write_text(BANK.read_text())
        tmp = str(BANK) + ".tmp.e564"
        Path(tmp).write_text(json.dumps([{
            "decisionVector": [float(v) for v in chrom],
            "problem": "trajectory",
            "challenge": "spoc-4-luna-tomato-logistics",
        }]))
        os.replace(tmp, BANK)
        # re-validate from disk
        re_dv = json.load(open(BANK))[0]["decisionVector"]
        re_mass, _ = official_eval(udp, re_dv)
        log(f"BANKED: {bank_mass:.2f} -> {new_mass:.2f} kg "
            f"(+{new_mass - bank_mass:.2f}); re-validated from disk: "
            f"{re_mass:.2f} kg; backup at {bak}")
    else:
        log(f"NOT banked: re-matched {new_mass:.2f} <= bank {bank_mass:.2f}")

    # follow-up stats: unused idE/idL
    used_e = {int(r[0]) for r, _, _ in final_rows}
    used_l = {int(r[1]) for r, _, _ in final_rows}
    log(f"unused after rematch: idE {nE - len(used_e)}, idL {nL - len(used_l)}")
    log("E-564 done")


if __name__ == "__main__":
    main()
