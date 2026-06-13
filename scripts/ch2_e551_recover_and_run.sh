#!/bin/bash
# One-shot recovery: kill dead E-550, clear its stale checkpoints,
# run E-551 DP-reject instrumentation (foreground, ~20 min).
set -x
pkill -f ch2_e550_medium_walk_slsqp_alns.py
sleep 3
pgrep -f ch2_e550_medium && { echo "E-550 still alive, aborting"; exit 1; }
rm -f /tmp/ch2_e550_ckpt_chain*.json /tmp/ch2_e550_chain*_hist.jsonl
cd /home/julian/Projects/esa_spoc_26_3
/home/julian/micromamba/envs/spoc26/bin/python \
    scripts/ch2_e551_dp_reject_instrument.py 2>&1 \
    | tee runs/ch2/e551_reject_instrument.log
