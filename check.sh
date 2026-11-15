#!/usr/bin/env bash
# Quick health check of the three infrastructure services
echo "--- containers ---"; docker compose ps
echo "--- postgres ---"; docker compose exec -T postgres psql -U app -d inventory -c "select 'postgres ok' as status;"
echo "--- redis ---"; docker compose exec -T redis redis-cli ping
echo "--- kafka ---"; docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic smoke --partitions 1 --replication-factor 1 && docker compose exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
