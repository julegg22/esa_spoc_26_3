#!/usr/bin/env bash
# Self-chaining: wait for the short-ToF augment to finish, swap the corrected
# table into the path the order-search loads, then run e617 (4-chain, 48h) on the
# CORRECTED edge set as the persistent never-stop occupant. nohup-safe, session-independent.
set -u
cd /home/julian/Projects/esa_spoc_26_3
FINE=/tmp/ch2_small_tcoupled_ultrafine.npz
V2=/tmp/ch2_small_tcoupled_ultrafine_v2.npz
AUGLOG=runs/ch2_v3/augment_small_shorttof.log
ts() { date '+%Y-%m-%d %H:%M:%S'; }

echo "[$(ts)] waiting for short-ToF augment to finish..."
until grep -q '\[done\]' "$AUGLOG"; do sleep 30; done
echo "[$(ts)] augment done."
if [ ! -s "$V2" ]; then echo "[$(ts)] ERROR: $V2 missing/empty — aborting swap"; exit 1; fi

cp "$FINE" "${FINE%.npz}.truncated_bak.npz"
cp "$V2" "$FINE"
echo "[$(ts)] swapped corrected table into $FINE (truncated backed up)"

echo "[$(ts)] launching e617 4-chain 48h on CORRECTED table"
micromamba run -n spoc26 python scripts/ch2_e617_dp_alns_cheapest_repair.py 4 48 \
    > runs/ch2_v3/e617_corrected_table.log 2>&1
echo "[$(ts)] e617-corrected exited"
