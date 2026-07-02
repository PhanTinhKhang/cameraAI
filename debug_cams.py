import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017/')
db = client.ai_camera
config = db.config.find_one({'type': 'cameras'})
if config:
    for c in config.get('cameras', []):
        cam_id = c.get("id")
        name = c.get("name")
        lat = c.get("lat")
        lng = c.get("lng")
        print(f"Camera: {cam_id}, name={name}, lat={lat}, lng={lng}")
