#!/usr/bin/env bash
# Part A: load sweep (normal operation). Part B: projector-lag scenarios. ~15 minutes total.
set -e
DUR=${1:-30}
run() { docker compose run --rm tools python -m app.loadgen --mode $1 --rate $2 --duration $DUR --warmup 8 --run-id $3 | tail -1; }
ctl() { docker compose run --rm tools python -m app.ctl "$@" >/dev/null; }
RUNS=""
ctl lag 20; ctl pause off
for RATE in 300 600 1000 1500; do
  for M in E V S; do
    ID=sw_${M}_r${RATE}; run $M $RATE $ID; RUNS="$RUNS $ID"; sleep 3
  done
done
for LAG in 500 2000; do
  ctl lag $LAG; sleep 3
  for M in E V S; do
    ID=lag${LAG}_${M}_r600; run $M 600 $ID; RUNS="$RUNS $ID"; sleep 3
  done
done
ctl lag 20
OUT=sweep_summary docker compose run --rm tools python -m app.analyze $RUNS
echo "saved: logs/sweep_summary.csv"
