#!/usr/bin/env bash
# Held-out scenario (lag values/timings not used in training). Modes E, S, H1, H5, A1, A5 (H/A at residual-inconsistency targets 1% and 5%) in shuffled order per repetition.
set -e
REPS=${1:-2}; RATE=${2:-400}; DUR=${3:-120}; START=${4:-1}
SCH="0:30,20:1200,45:20,60:400,90:2500,105:20"
drain() { sleep 8; docker compose exec -T postgres psql -U app -d inventory -qc "VACUUM items;" >/dev/null; }
RUNS=""
for SEED in $(seq $START $((START+REPS-1))); do
  for M in $(printf "E\nS\nH1\nH5\nA1\nA5\n" | shuf --random-source=<(yes $SEED)); do
    ID=ev_${M}_s${SEED}; MODE=${M:0:1}; OP=${M:1}; OP=${OP:-1}
    docker compose run --rm tools python -m app.loadgen --mode $MODE --op $OP --rate $RATE --duration $DUR --warmup 5 \
      --seed $((100+SEED)) --lag-schedule "$SCH" --run-id $ID | tail -1
    RUNS="$RUNS $ID"; drain
  done
done
docker compose run --rm -e OUT=eval_summary_from${START} tools python -m app.analyze $RUNS
docker compose run --rm tools python -m app.timeline ev_E_s${START} ev_S_s${START} ev_H1_s${START} ev_H5_s${START} ev_A1_s${START} ev_A5_s${START}
