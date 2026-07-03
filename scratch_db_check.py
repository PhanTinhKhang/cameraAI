import asyncio, motor.motor_asyncio

client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:27017')
db = client['ai_camera']

async def check():
    config = await db['config'].find_one({'type': 'cameras'})
    print('CAMERAS:')
    for c in config.get('cameras', []):
        print(f"  {c.get('id')}: lat={c.get('lat')}, lng={c.get('lng')}")
    
    users = await db['users'].find({}).to_list(10)
    print('\nUSERS:')
    for u in users:
        print(f"  {u.get('phone')}: name={u.get('name')}, lat={u.get('lat')}, lng={u.get('lng')}, radius={u.get('radius')}")

asyncio.run(check())
