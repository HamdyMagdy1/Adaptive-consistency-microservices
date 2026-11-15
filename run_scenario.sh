#!/usr/bin/env bash
# Usage: ./run_scenario.sh NAME RATE REPS "LAG_SCHEDULE" ["PAUSES"]   (resumable; modes shuffled per repetition)
set -eo pipefail
warm() { echo "warm-up (discarded)"; docker compose run --rm tools python -m app.loadgen --mode V --rate $1 --duration 25 --warmup 0 --run-id warmup_tmp >/dev/null 2>&1 || true; rm -f logs/warmup_tmp_*; sleep 5; }
SC=$1; RATE=$2; REPS=$3; SCH=$4; PAUSE=${5:-}; DUR=${DUR:-120}
drain() { sleep 8; docker compose exec -T postgres psql -U app -d inventory -qc "VACUUM items;" >/dev/null; }
warm $RATE
for SEED in $(seq 1 $REPS); do
  for M in $(printf "E\nS\nV\nH1\nH5\nA1\nA5\n" | shuf --random-source=<(yes "$SC$SEED")); do
    ID=${SC}_${M}_s${SEED}; MODE=${M:0:1}; OP=${M:1}; OP=${OP:-1}
    [ -f logs/${ID}_client.csv ] && { echo "skip $ID"; continue; }
    docker compose run --rm tools python -m app.loadgen --mode $MODE --op $OP --rate $RATE --duration $DUR --warmup 5 \
      --seed $((100+SEED)) --lag-schedule "$SCH" --pause "$PAUSE" --run-id $ID | tail -1
    drain
  done
done
RUNS=$(ls logs/${SC}_*_client.csv | sed -e 's#logs/##' -e 's#_client.csv##' | tr '\n' ' ')
docker compose run --rm -e OUT=final_${SC} tools python -m app.analyze $RUNS
docker compose run --rm -e OUT=tl_${SC} tools python -m app.timeline ${SC}_E_s1 ${SC}_S_s1 ${SC}_V_s1 ${SC}_H1_s1 ${SC}_H5_s1 ${SC}_A1_s1 ${SC}_A5_s1
