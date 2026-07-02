"""
Clean up duplicate user records in MongoDB.
Keeps only the LATEST record for each unique FCM token.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pymongo import MongoClient
from bson import ObjectId

client = MongoClient('mongodb://localhost:27017/')
db = client.ai_camera

users = list(db.users.find())
print(f"Total user records BEFORE cleanup: {len(users)}")

# Group by fcm_token
token_map = {}
for u in users:
    token = u.get('fcm_token', '')
    if not token or len(token) < 20:
        # Mark invalid tokens for deletion
        print(f"  🗑️ Will delete: name={repr(u.get('name'))}, token={repr(token)} (invalid/dummy)")
        db.users.delete_one({"_id": u["_id"]})
        continue
    if token not in token_map:
        token_map[token] = []
    token_map[token].append(u)

# For each token, keep only the newest record (by _id, which is time-based)
deleted = 0
for token, records in token_map.items():
    if len(records) > 1:
        # Sort by _id descending (newest first)
        records.sort(key=lambda x: x["_id"], reverse=True)
        newest = records[0]
        print(f"  ✅ Keeping: name={repr(newest.get('name'))}, radius={newest.get('radius')}, token=...{token[-20:]}")
        for old in records[1:]:
            print(f"  🗑️ Deleting duplicate: name={repr(old.get('name'))}, radius={old.get('radius')}, token=...{token[-20:]}")
            db.users.delete_one({"_id": old["_id"]})
            deleted += 1

remaining = list(db.users.find())
print(f"\nDeleted {deleted} duplicate records")
print(f"Total user records AFTER cleanup: {len(remaining)}")
print("\nRemaining users:")
for u in remaining:
    name = repr(u.get('name'))
    radius = u.get('radius')
    lat = u.get('lat')
    lng = u.get('lng')
    token = u.get('fcm_token', '')
    print(f"  {name}: radius={radius}, lat={lat}, lng={lng}, token=...{token[-20:]}")
