import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def run():
    client = AsyncIOMotorClient('mongodb://localhost:27017/')
    db = client['ai_camera']
    result = await db['users'].delete_many({})
    print(f'Cleared {result.deleted_count} users!')

asyncio.run(run())
