#!/usr/bin/env bash
# FINAL PIPELINE on the cloud VM. Usage: nohup ./run_final.sh RATE_MED RATE_HIGH [REPS] > logs/final.out 2>&1 &
# (1) collect training data  (2) train + freeze model  (3) three scenarios x REPS x 7 policies  (4) statistics. Resumable.
set -eo pipefail
RM=$1; RH=$2; REPS=${3:-10}
export RATES="$RM $RH"
./run_collect.sh
if [ ! -f logs/model.json ] || [ "${RETRAIN:-0}" = 1 ]; then ./run_train.sh | tee logs/train_report.txt; fi
LAGS="0:30,20:1200,45:20,60:400,90:2500,105:20"
./run_scenario.sh S1 $RM $REPS "$LAGS"
./run_scenario.sh S2 $RM $REPS "0:20" "30:15,75:8"
./run_scenario.sh S3 $RH $REPS "$LAGS"
docker compose run --rm tools python -m app.stats /logs/final_S1.csv /logs/final_S2.csv /logs/final_S3.csv | tee logs/final_stats.txt
echo "ALL DONE"
