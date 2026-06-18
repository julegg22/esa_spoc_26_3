#!/usr/bin/env bash
# Self-chaining runner for the Ch2 edge-probe queue (S2 -> M2 -> L2).
# Runs each to completion sequentially, nohup-safe, independent of any loop session.
# 3 workers each (M1's single-threaded CMA holds the 4th core).
set -u
cd /home/julian/Projects/esa_spoc_26_3
LOG=runs/ch2_v3
ts() { date '+%Y-%m-%d %H:%M:%S'; }
run() { echo "[$(ts)] START $1"; micromamba run -n spoc26 python "$2" $3 > "$4" 2>&1; echo "[$(ts)] DONE  $1 (exit $?)"; }

echo "[$(ts)] edge-probe chain begin (S2 -> M2 -> L2)"
run "S2 small edge probe" scripts/ch2_s2_shorttof_probe.py "30 3" "$LOG/S2_small_edgeprobe.log"
run "M2 medium edge probe" scripts/ch2_m2_shorttof_probe.py "30 3" "$LOG/M2_medium_edgeprobe.log"
run "L2 large edge probe" scripts/ch2_l2_shorttof_probe.py "3"     "$LOG/L2_large_edgeprobe.log"
echo "[$(ts)] edge-probe chain complete"
