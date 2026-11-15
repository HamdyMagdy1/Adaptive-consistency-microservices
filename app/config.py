import os
PG_DSN = os.getenv("PG_DSN", "postgresql://app:app@postgres:5432/inventory")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
KAFKA = os.getenv("KAFKA", "kafka:9092")
TOPIC = os.getenv("TOPIC", "item-updates")
LAG_MS = float(os.getenv("LAG_MS", "20"))        # base projector lag
GATEWAY = os.getenv("GATEWAY", "http://gateway:8000")
LOGDIR = os.getenv("LOGDIR", "/logs")
MODEL = os.getenv("MODEL", "/logs/model.json")
