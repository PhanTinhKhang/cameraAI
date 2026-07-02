import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pymongo import MongoClient
from collections import Counter

client = MongoClient('mongodb://localhost:27017/')
db = client.ai_camera
users = list(db.users.find())

# Group by fcm_token to find duplicates
tokens = [u.get('fcm_token','') for u in users if u.get('fcm_token')]
dups = Counter(tokens)
print('=== Duplicate FCM tokens ===')
for token, count in dups.items():
    if count > 1:
        print(f"  Token ...{token[-20:]}: {count} users share this token")

print()
print('=== All users ===')
for i, u in enumerate(users):
    name = repr(u.get('name'))
    radius = u.get('radius')
    lat = u.get('lat')
    lng = u.get('lng')
    fcm = u.get('fcm_token', '')
    fcm_end = fcm[-20:] if fcm else 'NONE'
    prefs = u.get('preferences', [])
    print(f"[{i}] name={name}, radius={radius}, lat={lat}, lng={lng}, prefs={prefs}, fcm=...{fcm_end}")
