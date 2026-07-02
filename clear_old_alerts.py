import asyncio
from datetime import datetime, timedelta
import os
import sys

from Arlert_BE.db import alerts_col

async def clear_old_alerts():
    # Calculate the threshold time (1 day ago)
    one_day_ago = datetime.now() - timedelta(days=1)
    
    print(f"Clearing alerts older than: {one_day_ago}")
    
    # The 'time' field is stored as a datetime object in MongoDB
    result = await alerts_col.delete_many({
        "time": {"$lt": one_day_ago}
    })
    
    print(f"Successfully deleted {result.deleted_count} old alerts from the database.")

if __name__ == "__main__":
    asyncio.run(clear_old_alerts())
