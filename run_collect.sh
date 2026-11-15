#!/usr/bin/env bash
# Training data: E-mode runs under varied lag schedules and two load levels. Usage: RATES="300 400" ./run_collect.sh  (resumable)
set -eo pipefail
warm() { echo "warm-up (discarded)"; docker compose run --rm tools python -m app.loadgen --mode V --rate $1 --duration 25 --warmup 0 --run-id warmup_tmp >/dev/null 2>&1 || true; rm -f logs/warmup_tmp_*; sleep 5; }
DUR=${DUR:-80}; RATES=${RATES:-"300 400"}
drain() { sleep 8; docker compose exec -T postgres psql -U app -d inventory -qc "VACUUM items;" >/dev/null; }
warm ${RATES%% *}
i=0
for SCH in "0:20,20:500,50:20,70:1000" "0:20,15:200,40:2000,65:20" "0:50,30:800,60:100,75:3000" "0:20,30:1500,60:300"; do
  i=$((i+1))
  for RATE in $RATES; do
    ID=col_T${i}_r${RATE}
    [ -f logs/${ID}_client.csv ] && { echo "skip $ID"; continue; }
    docker compose run --rm tools python -m app.loadgen --mode E --rate $RATE --duration $DUR --warmup 5 \
      --seed $((i*10+RATE/100)) --lag-schedule "$SCH" --run-id $ID | tail -1
    drain
  done
done
echo "collection done"
