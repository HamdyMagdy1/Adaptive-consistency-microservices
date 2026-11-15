#!/usr/bin/env bash
# Run once on a fresh Ubuntu VM, inside the cloned repo folder.
set -e
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
apt-get install -y tmux >/dev/null 2>&1 || true
chmod +x *.sh
docker compose --profile tools build
docker compose up -d kafka postgres redis gateway projector
sleep 45
docker compose ps
docker compose run --rm tools python -m app.seed 100000
nproc; free -h | head -2
echo "VM ready"
