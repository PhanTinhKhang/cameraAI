import asyncio
import os
import sys

from Arlert_BE.db import alerts_col

async def close_all_alerts():
    result = await alerts_col.update_many(
        {"status": {"$ne": "closed"}},
        {"$set": {"status": "closed"}}
    )
    print(f"Successfully closed {result.modified_count} alerts in the database.")

if __name__ == "__main__":
    asyncio.run(close_all_alerts())
