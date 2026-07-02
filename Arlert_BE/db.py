from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"

client = AsyncIOMotorClient(MONGO_URL)

db = client.ai_camera
alerts_col = db.alerts
users_col = db.users
config_col = db.config
