# Adaptive consistency for microservices (experiment code)

Step 2: gateway + projector + load generator + analysis with three static read strategies.

    docker compose build
    docker compose up -d kafka postgres redis gateway projector
    docker compose run --rm tools python -m app.seed 100000
    ./run_static.sh 300 40

Fault injection: `docker compose run --rm tools python -m app.ctl lag 500` (ms) or `pause on` / `pause off`.
