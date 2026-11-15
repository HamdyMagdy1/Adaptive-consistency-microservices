#!/usr/bin/env bash
# Part 1: fine saturation sweep (E and S) with CPU sampling. Part 2: time-varying lag scenario. ~15 min.
set -e
ctl() { docker compose run --rm tools python -m app.ctl "$@" >/dev/null; }
now() { python3 -c "import time;print(time.time())"; }
run() { docker compose run --rm tools python -m app.loadgen --mode $1 --rate $2 --duration $3 --warmup $4 --run-id $5 | tail -1; }

ctl lag 20; ctl pause off
# CPU sampler
( while true; do echo "$(date +%T) $(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' | tr '\n' ' ')"; sleep 4; done ) > logs/cpu_samples.txt 2>/dev/null &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

RUNS=""
for RATE in 400 500 600 700; do
  for M in E S; do ID=sat_${M}_r${RATE}; run $M $RATE 30 8 $ID; RUNS="$RUNS $ID"; sleep 3; done
done
OUT=sat_summary docker compose run --rm tools python -m app.analyze $RUNS

# Part 2: 120s run at 500 req/s; lag: 20ms -> 2000ms (t=30..60) -> 20ms -> 500ms (t=90..)
DRUNS=""
for M in E V S; do
  ID=dyn_${M}; ctl lag 20; sleep 2
  ( sleep 33; ctl lag 2000; sleep 30; ctl lag 20; sleep 30; ctl lag 500 ) &
  CP=$!
  run $M 500 120 0 $ID; wait $CP; DRUNS="$DRUNS $ID"; sleep 3
done
ctl lag 20
docker compose run --rm tools python -m app.timeline $DRUNS
OUT=dyn_summary docker compose run --rm tools python -m app.analyze $DRUNS
echo "--- CPU peak per container (from logs/cpu_samples.txt) ---"
python3 - <<'P'
import re,collections
mx=collections.defaultdict(float)
for l in open("logs/cpu_samples.txt"):
    for n,c in re.findall(r"(\S+) ([\d.]+)%",l): mx[n]=max(mx[n],float(c))
for n,c in sorted(mx.items(),key=lambda x:-x[1]): print(f"{n:55s} {c:6.0f}%")
P
