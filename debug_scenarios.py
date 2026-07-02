"""
Scenario Analysis: Multi-camera alert system behavior
=====================================================
Computes OSRM road distances between a user and both cameras,
then analyzes what happens in various alert scenarios.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio
import httpx
import math

# Camera positions (from MongoDB config)
CAM01 = {"id": "cam01", "name": "AI Camera 01 - Đà Nẵng Mỹ An", "lat": 16.03815771663389, "lng": 108.23923271123537}
CAM02 = {"id": "cam02", "name": "AI Camera 02 - Hoàng Hoa Thám", "lat": 16.05916590456129, "lng": 108.23723500346746}

# User positions (from MongoDB - the active user "ptk" with radius=1.5)
USER = {"name": "ptk", "lat": 16.0378569, "lng": 108.2387362, "radius": 1.5}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_road_distance(origin_lat, origin_lng, dest_lat, dest_lng):
    url = f"http://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=false"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            data = resp.json()
            if data.get("code") == "Ok":
                return data["routes"][0]["distance"] / 1000.0
    except Exception as e:
        print(f"OSRM error: {e}")
    return haversine(origin_lat, origin_lng, dest_lat, dest_lng)

async def main():
    print("=" * 70)
    print("SCENARIO ANALYSIS: Multi-Camera Alert System")
    print("=" * 70)
    
    # Calculate distances
    dist_cam01 = await get_road_distance(CAM01["lat"], CAM01["lng"], USER["lat"], USER["lng"])
    dist_cam02 = await get_road_distance(CAM02["lat"], CAM02["lng"], USER["lat"], USER["lng"])
    hav_cam01 = haversine(CAM01["lat"], CAM01["lng"], USER["lat"], USER["lng"])
    hav_cam02 = haversine(CAM02["lat"], CAM02["lng"], USER["lat"], USER["lng"])
    
    print(f"\n📍 User: {USER['name']} at ({USER['lat']}, {USER['lng']}), radius={USER['radius']}km")
    print(f"📷 cam01: {CAM01['name']}")
    print(f"   Haversine: {hav_cam01:.3f}km | Road: {dist_cam01:.3f}km | In range: {'✅ YES' if dist_cam01 <= USER['radius'] else '❌ NO'}")
    print(f"📷 cam02: {CAM02['name']}")
    print(f"   Haversine: {hav_cam02:.3f}km | Road: {dist_cam02:.3f}km | In range: {'✅ YES' if dist_cam02 <= USER['radius'] else '❌ NO'}")
    
    print("\n" + "=" * 70)
    print("SCENARIO 1: cam01 triggers accident (CLOSE to user)")
    print("=" * 70)
    print(f"  Distance: {dist_cam01:.3f}km <= {USER['radius']}km → {'PUSH NOTIFICATION SENT' if dist_cam01 <= USER['radius'] else 'NO PUSH'}")
    print(f"  WebSocket: broadcast() sends realtime alert to ALL connected clients")
    print(f"  Flutter app: _onNewAlertReceived() checks OSRM distance from phone GPS")
    print(f"    → Distance {dist_cam01:.3f}km <= {USER['radius']}km")
    if dist_cam01 <= USER['radius']:
        print(f"    → ✅ Shows popup, plays siren, shows local notification")
    else:
        print(f"    → ❌ Silently adds red marker to map, no popup/sound")
    
    print("\n" + "=" * 70)
    print("SCENARIO 2: cam02 triggers accident (FAR from user)")
    print("=" * 70)
    print(f"  Distance: {dist_cam02:.3f}km > {USER['radius']}km → {'PUSH NOTIFICATION SENT' if dist_cam02 <= USER['radius'] else 'NO PUSH'}")
    print(f"  WebSocket: broadcast() still sends realtime alert to ALL connected clients")
    print(f"  Flutter app: _onNewAlertReceived() checks OSRM distance from phone GPS")
    print(f"    → Distance {dist_cam02:.3f}km > {USER['radius']}km")
    if dist_cam02 <= USER['radius']:
        print(f"    → ✅ Shows popup, plays siren, shows local notification")
    else:
        print(f"    → ❌ Silently adds red marker to map, no popup/sound")
    
    print("\n" + "=" * 70)
    print("SCENARIO 3: cam02 triggers FIRST, then cam01 triggers 30s later")
    print("=" * 70)
    print(f"  T+0s: cam02 alert arrives")
    print(f"    Backend push: {dist_cam02:.3f}km > {USER['radius']}km → NO PUSH")
    print(f"    Flutter WS: distance check → OUT OF RANGE → red marker only, no popup")
    print(f"  T+30s: cam01 alert arrives")
    print(f"    Backend push: {dist_cam01:.3f}km <= {USER['radius']}km → PUSH SENT ✅")
    print(f"    Flutter WS: distance check → IN RANGE → popup + siren + notification ✅")
    print(f"  Result: User only alerted for the nearby incident ✅")
    
    print("\n" + "=" * 70)
    print("SCENARIO 4: cam01 and cam02 trigger SIMULTANEOUSLY")
    print("=" * 70)
    print(f"  Both alerts processed sequentially by FastAPI (async but single-threaded)")
    print(f"  cam01: {dist_cam01:.3f}km → PUSH SENT ✅")
    print(f"  cam02: {dist_cam02:.3f}km → NO PUSH ❌")
    print(f"  Flutter WS: receives both alerts via broadcast()")
    print(f"    cam01: IN RANGE → popup + siren ✅")
    print(f"    cam02: OUT OF RANGE → red marker only ❌")
    print(f"  ⚠️ ISSUE: If cam02 WS message arrives first, map animates to cam02 then cam01")
    
    print("\n" + "=" * 70)
    print("SCENARIO 5: App is CLOSED/KILLED")
    print("=" * 70)
    print(f"  WebSocket: DEAD (no WS connection when app is killed)")
    print(f"  Push notification is the ONLY way to reach the user")
    print(f"  cam01 alert: Backend sends FCM data-only push with priority=high")
    print(f"    → _firebaseMessagingBackgroundHandler() wakes app")
    print(f"    → Shows local notification with title + body")
    print(f"    → User taps notification → app opens → navigates to alert")
    print(f"  cam02 alert: Backend skips FCM (out of range)")
    print(f"    → User sees NOTHING (correct behavior)")
    
    print("\n" + "=" * 70)
    print("KNOWN ISSUES & EDGE CASES")
    print("=" * 70)
    print("""
  1. DUPLICATE USERS: You have 10 user records with different FCM tokens.
     The backend loops ALL of them, sending pushes to stale tokens.
     Stale tokens may cause FCM errors, but now each error is caught
     individually so it won't kill the loop.
     
  2. OSRM RATE LIMITING: Backend calls OSRM for EACH user (10 calls per alert).
     OSRM public API may rate-limit or timeout, causing distance calculation
     to fall back to haversine (which gives shorter, straight-line distances).
     
  3. DATA-ONLY FCM + BATTERY OPTIMIZATION: Some Android OEMs (Xiaomi, Oppo, 
     Vivo) aggressively kill background processes. Data-only FCM messages
     may not wake the app. We now set AndroidConfig(priority="high") to
     help, but it's not guaranteed on all devices.
     
  4. CIRCLE RADIUS HARDCODED: The red circle on the map is hardcoded to
     2000m radius regardless of user's preferred radius setting.
""")

asyncio.run(main())
