import asyncio
import os
import sys

from Arlert_BE.db import alerts_col

async def inspect():
    count = await alerts_col.count_documents({})
    print(f"Total alerts in DB: {count}")
    
    print("\nSample alerts:")
    cursor = alerts_col.find().sort("time", 1).limit(5)
    async for a in cursor:
        print(f"ID: {a.get('_id')}, time: {a.get('time')} (type: {type(a.get('time'))})")

if __name__ == "__main__":
    asyncio.run(inspect())
