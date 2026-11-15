#!/usr/bin/env bash
# Runs the three static read strategies one after another, then prints a summary table.
set -e
RATE=${1:-300}; DUR=${2:-40}
for m in E V S; do
  docker compose run --rm tools python -m app.loadgen --mode $m --rate $RATE --duration $DUR --warmup 10 --run-id static_$m
done
docker compose run --rm tools python -m app.analyze static_E static_V static_S
