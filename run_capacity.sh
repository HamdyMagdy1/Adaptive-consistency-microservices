#!/usr/bin/env bash
# Capacity calibration on the final machine: E and S at increasing rates (~12 min). Send the table back.
set -eo pipefail
warm() { echo "warm-up (discarded)"; docker compose run --rm tools python -m app.loadgen --mode V --rate $1 --duration 25 --warmup 0 --run-id warmup_tmp >/dev/null 2>&1 || true; rm -f logs/warmup_tmp_*; sleep 5; }
drain() { sleep 6; docker compose exec -T postgres psql -U app -d inventory -qc "VACUUM items;" >/dev/null; }
RUNS=""
RATES=${RATES:-"400 600 800 1000 1300 1600"}
warm ${RATES%% *}
for RATE in ${RATES:-"400 600 800 1000 1300 1600"}; do
  for M in E S; do
    ID=cap_${M}_r${RATE}
    docker compose run --rm tools python -m app.loadgen --mode $M --rate $RATE --duration 30 --warmup 8 --run-id $ID | tail -1
    RUNS="$RUNS $ID"; drain
  done
done
docker compose run --rm -e OUT=capacity tools python -m app.analyze $RUNS
