#!/usr/bin/env bash
# Held-out scenario (lag values/timings not used in training). Modes E, S, H1, H5, A1, A5 (H/A at residual-inconsistency targets 1% and 5%) in shuffled order per repetition.
set -e
REPS=${1:-2}; RATE=${2:-400}; DUR=${3:-120}
SCH="0:30,20:1200,45:20,60:400,90:2500,105:20"
drain() { sleep 8; docker compose exec -T postgres psql -U app -d inventory -qc "VACUUM items;" >/dev/null; }
RUNS=""
for SEED in $(seq 1 $REPS); do
  for M in $(printf "E\nS\nH1\nH5\nA1\nA5\n" | shuf --random-source=<(yes $SEED)); do
    ID=ev_${M}_s${SEED}; MODE=${M:0:1}; OP=${M:1}; OP=${OP:-1}
    docker compose run --rm tools python -m app.loadgen --mode $MODE --op $OP --rate $RATE --duration $DUR --warmup 5 \
      --seed $((100+SEED)) --lag-schedule "$SCH" --run-id $ID | tail -1
    RUNS="$RUNS $ID"; drain
  done
done
OUT=eval_summary docker compose run --rm tools python -m app.analyze $RUNS
docker compose run --rm tools python -m app.timeline ev_E_s1 ev_S_s1 ev_H1_s1 ev_H5_s1 ev_A1_s1 ev_A5_s1
