#!/bin/bash
# Auto-pipeline: wait for current sweep, then chain Tier 1A → 1B → 1C → rebank → re-polish.
# Each phase banks an interim trajectory.json. User can submit at any milestone.

set -e
SWEEP_LOG="runs/ch1/28_production_sweep_v3.log"
PIPELINE_LOG="runs/ch1/30_auto_pipeline.log"
PYBIN="/home/julian/micromamba/envs/spoc26/bin/python"

cd /home/julian/Projects/esa_spoc_26_3

log() {
  echo "[$(date +%T)] $1" | tee -a "$PIPELINE_LOG"
}

show_bank() {
  PYTHONPATH=src $PYBIN -c '
import json
from esa_spoc_26.ch1_trajectory import LtlTrajectory
udp = LtlTrajectory("reference/SpOC4/Challenge 1 Luna Tomato Logistics/")
bank = json.load(open("solutions/upload/trajectory.json"))
dv = bank[0]["decisionVector"]
f = udp.fitness(dv)[0]
n_active = sum(1 for i in range(0, len(dv), 21) if dv[i] >= 0)
print(f"  Mass: {-f:.0f} kg, transfers: {n_active}")
'
}

log "===== AUTO-PIPELINE START ====="

# Phase 0: Wait for current sweep to finish
log "Phase 0: waiting for production sweep to finish..."
while pgrep -f ch1_production_sweep > /dev/null; do
  sleep 120
  TAIL=$(tail -1 "$SWEEP_LOG" 2>/dev/null)
  log "Sweep still running, last: $TAIL"
done
log "Phase 0: sweep complete."
log "Baseline bank:"
show_bank | tee -a "$PIPELINE_LOG"

# Save sweep results JSON if it exists (for downstream rebank)
if [ ! -f "runs/ch1/sweep_results.json" ]; then
  log "WARN: sweep_results.json missing (running sweep predates that feature)"
fi

# Phase 1A: per-pair Nelder-Mead polish
log "===== Phase 1A: Nelder-Mead polish per pair ====="
PYTHONPATH=src $PYBIN -u scripts/ch1_polish_chromosome.py 8 >> "$PIPELINE_LOG" 2>&1 || log "Phase 1A had errors"
log "After 1A:"
show_bank | tee -a "$PIPELINE_LOG"

# Phase 1B: 3-impulse mid-course polish
log "===== Phase 1B: 3-impulse mid-course polish ====="
PYTHONPATH=src $PYBIN -u scripts/ch1_3impulse_polish.py 8 >> "$PIPELINE_LOG" 2>&1 || log "Phase 1B had errors"
log "After 1B:"
show_bank | tee -a "$PIPELINE_LOG"

# Phase 1C: extended sweep on pairs #500-#2000
log "===== Phase 1C: extended sweep on pairs #500-#2000 ====="
PYTHONPATH=src $PYBIN -u scripts/ch1_extend_sweep.py 500 2000 8 >> "$PIPELINE_LOG" 2>&1 || log "Phase 1C had errors"

# Phase 1D: Hungarian rebank with all candidates
log "===== Phase 1D: Hungarian rebank combining all results ====="
PYTHONPATH=src $PYBIN -u scripts/ch1_hungarian_rebank.py runs/ch1/extended_results.json >> "$PIPELINE_LOG" 2>&1 || log "Phase 1D had errors"
log "After 1D:"
show_bank | tee -a "$PIPELINE_LOG"

# Phase 1E: re-polish after rebank (new transfers may need polish)
log "===== Phase 1E: re-polish ====="
PYTHONPATH=src $PYBIN -u scripts/ch1_polish_chromosome.py 8 >> "$PIPELINE_LOG" 2>&1 || log "Phase 1E.A had errors"
PYTHONPATH=src $PYBIN -u scripts/ch1_3impulse_polish.py 8 >> "$PIPELINE_LOG" 2>&1 || log "Phase 1E.B had errors"

log "===== AUTO-PIPELINE COMPLETE ====="
log "Final bank:"
show_bank | tee -a "$PIPELINE_LOG"
