"""
Scenario Analysis with 5km user radius
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio
import httpx
import math

CAM01 = {"id": "cam01", "name": "AI Camera 01 - Da Nang My An", "lat": 16.03815771663389, "lng": 108.23923271123537}
CAM02 = {"id": "cam02", "name": "AI Camera 02 - Hoang Hoa Tham", "lat": 16.05916590456129, "lng": 108.23723500346746}
USER = {"name": "ptk", "lat": 16.0378569, "lng": 108.2387362, "radius": 5.0}

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
        pass
    return haversine(origin_lat, origin_lng, dest_lat, dest_lng)

async def main():
    dist_cam01 = await get_road_distance(CAM01["lat"], CAM01["lng"], USER["lat"], USER["lng"])
    dist_cam02 = await get_road_distance(CAM02["lat"], CAM02["lng"], USER["lat"], USER["lng"])
    hav_cam01 = haversine(CAM01["lat"], CAM01["lng"], USER["lat"], USER["lng"])
    hav_cam02 = haversine(CAM02["lat"], CAM02["lng"], USER["lat"], USER["lng"])
    
    print("=" * 70)
    print("SCENARIO ANALYSIS WITH 5km RADIUS")
    print("=" * 70)
    
    print(f"\nUser: {USER['name']} at ({USER['lat']}, {USER['lng']}), radius={USER['radius']}km")
    print(f"\ncam01: {CAM01['name']}")
    print(f"  Haversine: {hav_cam01:.3f}km | Road: {dist_cam01:.3f}km")
    print(f"  {dist_cam01:.3f}km <= {USER['radius']}km ? {'YES - IN RANGE' if dist_cam01 <= USER['radius'] else 'NO - OUT OF RANGE'}")
    
    print(f"\ncam02: {CAM02['name']}")
    print(f"  Haversine: {hav_cam02:.3f}km | Road: {dist_cam02:.3f}km")
    print(f"  {dist_cam02:.3f}km <= {USER['radius']}km ? {'YES - IN RANGE' if dist_cam02 <= USER['radius'] else 'NO - OUT OF RANGE'}")
    
    print("\n" + "=" * 70)
    print("SCENARIO A: cam01 triggers (close camera)")
    print("=" * 70)
    in_range = dist_cam01 <= USER['radius']
    print(f"  Road distance: {dist_cam01:.3f}km")
    print(f"  User radius: {USER['radius']}km")
    print(f"  In range: {'YES' if in_range else 'NO'}")
    print(f"  Push notification: {'SENT' if in_range else 'NOT SENT'}")
    print(f"  App popup/siren: {'YES' if in_range else 'NO'}")
    
    print("\n" + "=" * 70)
    print("SCENARIO B: cam02 triggers (far camera)")
    print("=" * 70)
    in_range = dist_cam02 <= USER['radius']
    print(f"  Road distance: {dist_cam02:.3f}km")
    print(f"  User radius: {USER['radius']}km")
    print(f"  In range: {'YES' if in_range else 'NO'}")
    print(f"  Push notification: {'SENT' if in_range else 'NOT SENT'}")
    print(f"  App popup/siren: {'YES' if in_range else 'NO'}")
    
    print("\n" + "=" * 70)
    print("SCENARIO C: Both cameras trigger simultaneously")
    print("=" * 70)
    cam01_in = dist_cam01 <= USER['radius']
    cam02_in = dist_cam02 <= USER['radius']
    print(f"  cam01: {dist_cam01:.3f}km - {'IN RANGE -> Push + Popup + Siren' if cam01_in else 'OUT OF RANGE -> Red marker only'}")
    print(f"  cam02: {dist_cam02:.3f}km - {'IN RANGE -> Push + Popup + Siren' if cam02_in else 'OUT OF RANGE -> Red marker only'}")
    
    if cam01_in and cam02_in:
        print(f"\n  IMPORTANT: Both cameras are within {USER['radius']}km!")
        print(f"  User receives TWO push notifications (one per camera)")
        print(f"  User sees TWO popup alerts sequentially")
        print(f"  User hears siren TWICE")
        print(f"  Map shows TWO red markers with {USER['radius']*1000:.0f}m circles")
    elif cam01_in and not cam02_in:
        print(f"\n  Only cam01 triggers full alert. cam02 shows red marker silently.")
    elif not cam01_in and cam02_in:
        print(f"\n  Only cam02 triggers full alert. cam01 shows red marker silently.")
    else:
        print(f"\n  Neither camera is in range. User sees red markers only.")
    
    print("\n" + "=" * 70)
    print("SCENARIO D: cam02 triggers first, cam01 triggers 30s later")
    print("=" * 70)
    print(f"  T+0s:  cam02 ({dist_cam02:.3f}km) - {'ALERT!' if cam02_in else 'silent red marker'}")
    print(f"  T+30s: cam01 ({dist_cam01:.3f}km) - {'ALERT!' if cam01_in else 'silent red marker'}")
    if cam01_in and cam02_in:
        print(f"  Result: User gets alerted TWICE (both within {USER['radius']}km)")
    
    print("\n" + "=" * 70)
    print("SCENARIO E: App is CLOSED")
    print("=" * 70)
    print(f"  cam01 ({dist_cam01:.3f}km): {'FCM push SENT - user sees notification' if cam01_in else 'No push - user sees nothing'}")
    print(f"  cam02 ({dist_cam02:.3f}km): {'FCM push SENT - user sees notification' if cam02_in else 'No push - user sees nothing'}")
    
    print("\n" + "=" * 70)
    print("KEY DIFFERENCE vs 1.5km RADIUS")
    print("=" * 70)
    print(f"  With 1.5km radius:")
    print(f"    cam01 ({dist_cam01:.3f}km): IN RANGE")
    print(f"    cam02 ({dist_cam02:.3f}km): OUT OF RANGE")
    print(f"  With 5.0km radius:")
    print(f"    cam01 ({dist_cam01:.3f}km): {'IN RANGE' if dist_cam01 <= 5.0 else 'OUT OF RANGE'}")
    print(f"    cam02 ({dist_cam02:.3f}km): {'IN RANGE' if dist_cam02 <= 5.0 else 'OUT OF RANGE'}")
    
    if dist_cam02 <= 5.0:
        print(f"\n  With 5km radius, cam02 is NOW IN RANGE!")
        print(f"  This means the user will receive alerts from BOTH cameras.")
        print(f"  The red circle on the map will be 5000m radius (2.5x larger).")
    else:
        print(f"\n  Even with 5km radius, cam02 ({dist_cam02:.3f}km) is STILL out of range.")

asyncio.run(main())
