#!/bin/bash
# Wait for the extended-T2 polish to finish, then launch Phase A.
set -eu
POLISH_PID="${1:?need polish PID}"
LOG=/home/julian/Projects/esa_spoc_26_3/runs/ch1/63_phase_a.log
cd /home/julian/Projects/esa_spoc_26_3

echo "[$(date '+%T')] Waiting for polish PID $POLISH_PID to finish..." > "$LOG"
while kill -0 "$POLISH_PID" 2>/dev/null; do
    sleep 60
done
echo "[$(date '+%T')] Polish finished. Launching Phase A." >> "$LOG"

exec /home/julian/micromamba/envs/spoc26/bin/python -u \
    scripts/ch1_phase_a_full_matrix.py 30 8 >> "$LOG" 2>&1
