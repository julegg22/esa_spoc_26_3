#!/usr/bin/env bash
# Ch2 v2 heavy-compute chain: joint (td, tof) window precompute + MW CP-SAT.
# The single-tof multi-window precompute (run 1) was INFEASIBLE because
# 48 cheap legs at median tof=33d sum to ~1312d >> 200d horizon. v2
# scans (td × tof) jointly to find short-tof low-Δv windows.
set -u
cd /home/julian/Projects/esa_spoc_26_3
mkdir -p runs/ch2_v2

PY="micromamba run -n spoc26 python"
LOG=runs/ch2_v2

ts() { date +%Y-%m-%dT%H:%M:%S; }

echo "[$(ts)] === [1/2] precompute_windows_2d (joint td×tof) ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp windows2d \
  >$LOG/01_windows2d.json 2>$LOG/01_windows2d.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === [2/2] Multi-window CP-SAT v2 (600 s) DECISIVE ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_cpsat_mw 600 \
  >$LOG/02_cpsat_mw.json 2>$LOG/02_cpsat_mw.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === V2 CHAIN DONE ===" | tee -a $LOG/00_master.log
