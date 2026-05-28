#!/bin/bash
set -eu
CMAES_PID="${1:?need CMA-ES PID}"
LOG=/home/julian/Projects/esa_spoc_26_3/runs/ch1/66_tier1a.log
cd /home/julian/Projects/esa_spoc_26_3
echo "[$(date '+%T')] Waiting for CMA-ES PID $CMAES_PID to finish..." > "$LOG"
while kill -0 "$CMAES_PID" 2>/dev/null; do sleep 60; done
echo "[$(date '+%T')] CMA-ES finished. Launching Tier 1A." >> "$LOG"
exec /home/julian/micromamba/envs/spoc26/bin/python -u \
    scripts/ch1_tier1a_extended.py 8 15 >> "$LOG" 2>&1
