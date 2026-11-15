"""Create and fill the items table and the Redis read model."""
import asyncio, sys
import asyncpg, redis.asyncio as aioredis
from . import config as C

async def main(n):
    pg = await asyncpg.connect(C.PG_DSN)
    await pg.execute("DROP TABLE IF EXISTS items; CREATE TABLE items(id int primary key, stock int not null, version int not null);")
    await pg.execute("INSERT INTO items SELECT g, 1000000, 0 FROM generate_series(1,$1) g", n)
    r = aioredis.from_url(C.REDIS_URL)
    await r.flushdb()
    for start in range(1, n + 1, 10000):
        p = r.pipeline()
        for i in range(start, min(start + 10000, n + 1)):
            p.hset(f"i:{i}", mapping={"v": 0, "s": 1000000})
        await p.execute()
    print(f"seeded {n} items")
    await pg.close(); await r.aclose()

if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 100000))
