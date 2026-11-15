#!/usr/bin/env bash
# Usage: RATES="300 400" ./run_train.sh   (RATES must equal the ones used in run_collect.sh)
set -e
set -- ${RATES:-300 400}; A=$1; B=$2
docker compose run --rm tools python -m app.train \
  --train col_T1_r$A,col_T1_r$B,col_T2_r$A,col_T3_r$B,col_T4_r$B,col_T3_r$A \
  --val col_T2_r$B,col_T4_r$A
