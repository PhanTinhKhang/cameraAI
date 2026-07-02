import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def f():
    db=AsyncIOMotorClient('mongodb://localhost:27017')['ai_camera']
    users = await db.users.find().to_list(None)
    for u in users:
        print(u.get('name'), u.get('lat'), u.get('lng'))

asyncio.run(f())
