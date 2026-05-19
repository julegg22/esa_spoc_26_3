#!/usr/bin/env bash
# Ch2 heavy-compute chain (T-008 plan): Q6 large → TW prototype →
# precompute_windows → multi-window CP-SAT. Serial, one micromamba run
# at a time (L-004). Each stage writes its log under runs/.
set -u
cd /home/julian/Projects/esa_spoc_26_3
mkdir -p runs/ch2_chain

PY="micromamba run -n spoc26 python"
LOG=runs/ch2_chain
HARD="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/hard.kttsp"
EASY="reference/SpOC4/Challenge 2 Keplerian Tomato Traveling Salesperson Problem/problems/easy.kttsp"

echo "=== [1/4] Q6 LARGE structure (sample=60) ===" | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp structacc "$HARD" 60 \
  >$LOG/01_q6_large.json 2>$LOG/01_q6_large.err
echo "rc=$?" | tee -a $LOG/00_master.log

echo "=== [2/4] TW prototype (180 s, easy=small) ===" | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_cpsat_tw 180 \
  >$LOG/02_cpsat_tw.json 2>$LOG/02_cpsat_tw.err
echo "rc=$?" | tee -a $LOG/00_master.log

echo "=== [3/4] precompute_windows (parallel mp.Pool) ===" | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_kttsp windows \
  >$LOG/03_windows.json 2>$LOG/03_windows.err
echo "rc=$?" | tee -a $LOG/00_master.log

echo "=== [4/4] Multi-window CP-SAT (600 s) DECISIVE ===" | tee -a $LOG/00_master.log
$PY -m esa_spoc_26.ch2_cpsat_mw 600 \
  >$LOG/04_cpsat_mw.json 2>$LOG/04_cpsat_mw.err
echo "rc=$?" | tee -a $LOG/00_master.log

echo "=== CHAIN DONE ===" | tee -a $LOG/00_master.log
