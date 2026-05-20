#!/usr/bin/env bash
# Ch2 heavy-compute chain (T-008 plan).
# Stage order revised: decisive multi-window CP-SAT first (small),
# then structure probes for medium/large if time. Each stage = one
# micromamba run, sequential per L-04 startup lock.
set -u
cd /home/julian/Projects/esa_spoc_26_3
mkdir -p runs/ch2_chain

PY="micromamba run -n spoc26 python"
LOG=runs/ch2_chain
HARD="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp"
MED="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/medium.kttsp"

ts() { date +%Y-%m-%dT%H:%M:%S; }

echo "[$(ts)] === [1/5] TW (single-window) PROTOTYPE (180 s, small) ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_cpsat_tw 180 \
  >$LOG/01_cpsat_tw.json 2>$LOG/01_cpsat_tw.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === [2/5] precompute_windows (small, parallel mp.Pool) ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp windows \
  >$LOG/02_windows.json 2>$LOG/02_windows.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === [3/5] Multi-window CP-SAT (600 s) DECISIVE ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_cpsat_mw 600 \
  >$LOG/03_cpsat_mw.json 2>$LOG/03_cpsat_mw.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === [4/5] Q6 MEDIUM structure (sample=30) ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp structacc "$MED" 30 \
  >$LOG/04_q6_medium.json 2>$LOG/04_q6_medium.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === [5/5] Q6 LARGE structure (sample=30) ===" \
  | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp structacc "$HARD" 30 \
  >$LOG/05_q6_large.json 2>$LOG/05_q6_large.err
echo "[$(ts)] rc=$?" | tee -a $LOG/00_master.log

echo "[$(ts)] === CHAIN DONE ===" | tee -a $LOG/00_master.log
