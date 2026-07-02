# =====================
# alert_server.py
# =====================
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import json
import os
import shutil
import httpx
import math
import asyncio
import time
import firebase_admin
from firebase_admin import credentials, messaging

# Initialize Firebase Admin SDK
cred_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "firebase-adminsdk.json")
try:
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("🔥 Firebase Admin SDK Initialized using JSON key")
    else:
        firebase_admin.initialize_app()
        print("🔥 Firebase Admin SDK Initialized using Application Default Credentials (ADC)")
except Exception as e:
    print("⚠️ Firebase Admin SDK failed to initialize:", e)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

_distance_cache = {}  # key: (rounded coords) -> (distance_km, timestamp)
_CACHE_TTL = 60  # seconds

async def get_road_distance(origin_lat, origin_lng, dest_lat, dest_lng):
    # Round to 4 decimal places (~11m precision) for cache key
    cache_key = (round(origin_lat, 4), round(origin_lng, 4), round(dest_lat, 4), round(dest_lng, 4))
    now = time.time()
    
    # Check cache
    if cache_key in _distance_cache:
        cached_dist, cached_time = _distance_cache[cache_key]
        if now - cached_time < _CACHE_TTL:
            return cached_dist
    
    url = f"http://router.project-osrm.org/route/v1/driving/{origin_lng},{origin_lat};{dest_lng},{dest_lat}?overview=false"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            data = resp.json()
            if data.get("code") == "Ok":
                distance_km = data["routes"][0]["distance"] / 1000.0
                _distance_cache[cache_key] = (distance_km, now)
                return distance_km
    except Exception as e:
        print("OSRM API error:", e)
    
    # Fallback to haversine if API fails
    fallback = haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    print(f"  ⚠️ Using haversine fallback: {fallback:.3f}km (OSRM unavailable)")
    return fallback

from db import alerts_col, users_col

# =====================
# APP
# =====================
app = FastAPI()

# =====================
# PATH CONFIG
# =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_DIR = os.path.join(BASE_DIR, "alerts")
TEST_VIDEO_DIR = os.path.join(BASE_DIR, "videos")

print("📁 VIDEO_DIR =", VIDEO_DIR)

# =====================
# ARLERT.PY URL
# =====================
ARLERT_SERVICE_URL = "http://localhost:8080"

# =====================
# CORS
# =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================
# STARTUP & HEALTH
# =====================
from db import client

@app.on_event("startup")
async def startup_event():
    print("🚀 Running startup tasks... creating MongoDB indexes")
    try:
        await alerts_col.create_index([("time", -1)])
        await users_col.create_index("phone", unique=True)
        print("✅ MongoDB indexes created successfully")
    except Exception as e:
        print("⚠️ Failed to create MongoDB indexes:", e)

@app.get("/health")
async def health_check():
    try:
        # Check DB connection
        await client.admin.command('ping')
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

# =====================
# STATIC VIDEO
# =====================
app.mount(
    "/videos",
    StaticFiles(directory=VIDEO_DIR),
    name="videos"
)

CHAT_MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_media")
os.makedirs(CHAT_MEDIA_DIR, exist_ok=True)

app.mount(
    "/chat_media",
    StaticFiles(directory=CHAT_MEDIA_DIR),
    name="chat_media"
)

class ChatMessage(BaseModel):
    text: str
    type: str = "text"
    content: str = ""
    sender: str
    sender_id: str
    name: str

class ForceCall(BaseModel):
    force: str

# =====================
# WEBSOCKET CLIENTS
# =====================
clients: set[WebSocket] = set()

@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    print(f"🟢 WS CONNECTED | clients = {len(clients)}")

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)
        print(f"🔴 WS DISCONNECTED | clients = {len(clients)}")

async def broadcast(alert: dict):
    dead = []
    for ws in clients:
        try:
            # Chuyển ObjectId thành chuỗi trước khi broadcast
            alert_copy = dict(alert)
            if "_id" in alert_copy and isinstance(alert_copy["_id"], ObjectId):
                alert_copy["_id"] = str(alert_copy["_id"])
            await ws.send_text(json.dumps(alert_copy, default=str))
        except Exception as e:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)

# =====================
# CORE ALERTS
# =====================
@app.post("/alert")
async def receive_alert(alert: dict):
    # parse time
    if isinstance(alert.get("time"), str):
        alert["time"] = datetime.strptime(
            alert["time"], "%Y-%m-%d %H:%M:%S"
        )

    filename = os.path.basename(alert["video"])
    alert["video_url"] = f"http://localhost:8000/videos/{filename}"
    
    # Init new fields for Volunteer app
    alert["volunteers"] = []
    alert["status"] = "open"
    alert["rescue_sent"] = False
    alert["forces_called"] = []
    alert["false_alarm_reports"] = 0

    # Inject latest camera config (name, lat, lng) by matching camera_id
    config = await config_col.find_one({"type": "cameras"})
    if config and "cameras" in config:
        target_cam_id = alert.get("camera_id", "cam01")
        cam_config = next((c for c in config["cameras"] if c.get("id") == target_cam_id), None)
        if not cam_config and len(config["cameras"]) > 0:
            cam_config = config["cameras"][0] # fallback

        if cam_config:
            alert["location"] = cam_config.get("name", alert.get("location"))
            alert["lat"] = cam_config.get("lat", alert.get("lat"))
            alert["lng"] = cam_config.get("lng", alert.get("lng"))
            alert["stream"] = cam_config.get("stream", alert.get("stream"))
            alert["camera_id"] = target_cam_id

    # save DB
    result = await alerts_col.insert_one(alert)
    alert["_id"] = str(result.inserted_id)
    alert["time"] = alert["time"].strftime("%Y-%m-%d %H:%M:%S")

    # broadcast realtime
    await broadcast(alert)
    
    # Trigger Firebase Push Notification
    cam_lat = alert.get("lat")
    cam_lng = alert.get("lng")
    if cam_lat and cam_lng:
        print(f"📍 Push notification check: alert at ({cam_lat}, {cam_lng}), type={alert['type']}")
        cursor = users_col.find({"fcm_token": {"$exists": True, "$ne": ""}})
        sent_count = 0
        async for u in cursor:
            u_name = u.get("name", "unknown")
            u_lat = u.get("lat")
            u_lng = u.get("lng")
            u_prefs = u.get("preferences", [])
            u_radius = u.get("radius")
            u_token = u.get("fcm_token", "")
            
            if u_radius is None:
                u_radius = 2.0
            
            # Skip dummy/invalid tokens
            if not u_token or len(u_token) < 20:
                print(f"  ⏭️ [{u_name}] Skipped: invalid/dummy FCM token")
                continue
            
            # Check alert preference matching
            if alert["type"] not in u_prefs and len(u_prefs) > 0:
                print(f"  ⏭️ [{u_name}] Skipped: does not want '{alert['type']}' alerts (prefs={u_prefs})")
                continue
            
            # Check distance
            if u_lat and u_lng:
                try:
                    dist = await get_road_distance(cam_lat, cam_lng, u_lat, u_lng)
                    print(f"  📏 [{u_name}] Distance={dist:.2f}km, radius={u_radius}km", end="")
                    if dist <= u_radius:
                        print(" → IN RANGE, sending push...")
                        alert_title = f"🚨 PHÁT HIỆN {alert['type'].upper()} GẦN BẠN!"
                        alert_body = f"Cách vị trí của bạn {dist:.1f}km. Click để ứng cứu!"
                        message = messaging.Message(
                            notification=messaging.Notification(
                                title=alert_title,
                                body=alert_body,
                            ),
                            data={
                                "alert_id": str(alert["_id"]),
                                "type": alert["type"],
                                "is_data_notification": "true",
                                "title": alert_title,
                                "body": alert_body,
                            },
                            android=messaging.AndroidConfig(
                                priority="high",
                                notification=messaging.AndroidNotification(
                                    channel_id="alert_channel_id",
                                    sound="default"
                                )
                            ),
                            token=u_token,
                        )
                        try:
                            await asyncio.to_thread(messaging.send, message)
                            sent_count += 1
                            print(f"  ✅ [{u_name}] Push sent successfully!")
                        except Exception as send_err:
                            print(f"  ❌ [{u_name}] FCM send failed: {send_err}")
                    else:
                        print(" → OUT OF RANGE, skipped")
                except Exception as dist_err:
                    print(f"  ❌ [{u_name}] Distance calc failed: {dist_err}")
            else:
                print(f"  ⏭️ [{u_name}] Skipped: no lat/lng location stored")
        
        print(f"📲 Push notification summary: {sent_count} notifications sent")
    else:
        print("⚠️ Alert has no lat/lng, skipping push notifications")

    print("🚨 ALERT SAVED:", alert["type"])
    return {"status": "ok", "video_url": alert["video_url"]}

@app.get("/alerts")
async def get_alerts(limit: int = 5):
    cursor = alerts_col.find().sort("time", -1).limit(limit)
    alerts = []
    async for a in cursor:
        a["_id"] = str(a["_id"])
        a["time"] = a["time"].strftime("%Y-%m-%d %H:%M:%S")
        alerts.append(a)
    return alerts

@app.post("/test_push")
async def test_push():
    """Test endpoint: send a push notification to ALL registered users regardless of distance."""
    results = []
    cursor = users_col.find({"fcm_token": {"$exists": True, "$ne": "", "$ne": "dummy_token"}})
    async for u in cursor:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="🧪 TEST: Thông báo kiểm tra",
                    body="Nếu bạn thấy thông báo này, hệ thống hoạt động tốt!",
                ),
                data={
                    "is_data_notification": "true",
                    "title": "🧪 TEST: Thông báo kiểm tra",
                    "body": "Nếu bạn thấy thông báo này, hệ thống hoạt động tốt!",
                },
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        channel_id='alert_channel_id',
                        sound='default',
                        priority='max',
                        default_vibrate_timings=True,
                    ),
                ),
                token=u["fcm_token"],
            )
            resp = await asyncio.to_thread(messaging.send, message)
            results.append({"name": u.get("name"), "status": "sent", "response": resp})
            print(f"✅ Test push sent to {u.get('name')} (token: {u['fcm_token'][:20]}...)")
        except Exception as e:
            results.append({"name": u.get("name"), "status": "failed", "error": str(e)})
            print(f"❌ Test push FAILED for {u.get('name')}: {e}")
    return {"results": results}

# =====================
# DASHBOARD ENDPOINTS
# =====================
from db import config_col

@app.get("/api/config/cameras")
async def get_cameras():
    config = await config_col.find_one({"type": "cameras"})
    if config and "cameras" in config:
        return config["cameras"]
    # Default cameras
    return [{
        "id": "cam01",
        "name": "AI Camera 01 - Đại học Bách Khoa Đà Nẵng",
        "rtsp_url": 1,
        "lat": 16.075433810355626,
        "lng": 108.14969733956971
    }]

from typing import List

class OfferRequest(BaseModel):
    sdp: str
    type: str

@app.post("/offer/{cam_id}")
async def webrtc_offer_proxy(cam_id: str, offer: OfferRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8080/offer/{cam_id}",
                json={"sdp": offer.sdp, "type": offer.type},
                timeout=10.0
            )
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WebRTC proxy error: {str(e)}")

@app.post("/offer")
async def webrtc_offer_proxy_legacy(offer: OfferRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8080/offer/cam01",
                json={"sdp": offer.sdp, "type": offer.type},
                timeout=10.0
            )
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"WebRTC proxy error: {str(e)}")

@app.post("/api/config/cameras")
async def save_cameras(cameras: List[dict]):
    await config_col.update_one(
        {"type": "cameras"},
        {"$set": {"cameras": cameras}},
        upsert=True
    )
    return {"status": "ok"}

@app.post("/api/alerts/{alert_id}/close")
async def close_alert(alert_id: str):
    result = await alerts_col.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"status": "closed"}}
    )
    if result.modified_count > 0:
        await broadcast({"action": "alert_closed", "alert_id": alert_id})
        
        # Give bonus points to completed volunteers and notify them
        try:
            alert = await alerts_col.find_one({"_id": ObjectId(alert_id)})
            if alert and "volunteers" in alert:
                for v in alert["volunteers"]:
                    if v.get("status") != "completed":
                        continue
                    
                    user_id = v["user_id"]
                    user = await users_col.find_one({"_id": ObjectId(user_id)})
                    if user:
                        new_points = user.get("points", 0) + 25
                        new_badge = get_badge_from_points(new_points)
                        
                        await users_col.update_one(
                            {"_id": ObjectId(user_id)},
                            {"$set": {"points": new_points, "badge": new_badge}}
                        )
                        
                        if user.get("fcm_token"):
                            message = messaging.Message(
                                data={
                                    "is_data_notification": "true",
                                    "title": "Huy chương danh dự! 🌟",
                                    "body": "Hành động nghĩa hiệp của bạn vừa giúp đỡ cộng đồng. Tặng bạn 25 điểm cống hiến!",
                                },
                                token=user["fcm_token"]
                            )
                            await asyncio.to_thread(messaging.send, message)
        except Exception as e:
            print(f"Error giving rewards on close: {e}")
            
    return {"status": "ok"}

@app.post("/api/alerts/{alert_id}/rescue_sent")
async def rescue_sent(alert_id: str):
    result = await alerts_col.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"rescue_sent": True}}
    )
    if result.modified_count > 0:
        await broadcast({"action": "update", "id": alert_id, "rescue_sent": True})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

@app.post("/api/alerts/{alert_id}/call_force")
async def call_force(alert_id: str, payload: ForceCall):
    print(f"DEBUG: calling force {payload.force} for alert_id {alert_id}")
    alert = await alerts_col.find_one({"_id": ObjectId(alert_id)})
    print(f"DEBUG: found alert: {alert is not None}")
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    forces = alert.get("forces_called", [])
    if payload.force not in forces:
        forces.append(payload.force)
        
    result = await alerts_col.update_one(
        {"_id": ObjectId(alert_id)},
        {"$set": {"rescue_sent": True, "forces_called": forces}}
    )
    if result.modified_count > 0 or len(forces) > 0:
        await broadcast({"action": "update", "id": alert_id, "rescue_sent": True, "forces_called": forces})
        return {"status": "ok", "forces_called": forces}
    return {"status": "ok", "forces_called": forces}
@app.post("/api/alerts/{id}/chat")
async def add_chat_message(id: str, msg: ChatMessage):
    alert = await alerts_col.find_one({"_id": ObjectId(id)})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.get("status") == "closed":
        raise HTTPException(status_code=403, detail="Chat is closed")
        
    chat_doc = {
        "text": msg.text,
        "type": msg.type,
        "content": msg.content,
        "sender": msg.sender,
        "sender_id": msg.sender_id,
        "name": msg.name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    await alerts_col.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"messages": chat_doc}}
    )
    
    # Send specific chat_message event for frontend notifications
    noti_text = msg.text
    if msg.type == 'image':
        noti_text = f"Đã gửi 1 ảnh"
    elif msg.type == 'audio':
        noti_text = f"Đã gửi 1 tin nhắn thoại"
        
    await broadcast({
        "action": "chat_message",
        "alert_id": id,
        "message": chat_doc,
        "text": noti_text,
        "type": msg.type,
        "name": msg.name
    })
    
    updated_alert = await alerts_col.find_one({"_id": ObjectId(id)})
    if updated_alert:
        updated_alert["_id"] = str(updated_alert["_id"])
        updated_alert["action"] = "update"
        await broadcast(updated_alert)
        
    return {"status": "ok"}

@app.post("/api/alerts/{id}/chat/media")
async def upload_chat_media(id: str, file: UploadFile = File(...)):
    alert = await alerts_col.find_one({"_id": ObjectId(id)})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.get("status") == "closed":
        raise HTTPException(status_code=403, detail="Chat is closed")
        
    # Tên file unique
    file_ext = os.path.splitext(file.filename)[1]
    timestamp = int(datetime.now().timestamp() * 1000)
    new_filename = f"media_{id}_{timestamp}{file_ext}"
    file_path = os.path.join(CHAT_MEDIA_DIR, new_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # file_url = f"http://localhost:8000/chat_media/{new_filename}"
    file_url = f"/chat_media/{new_filename}"
    return {"status": "ok", "url": file_url}

# =====================
# MOBILE APP ENDPOINTS
# =====================
class RegisterUser(BaseModel):
    name: str
    phone: str
    fcm_token: str
    skills: str = ""
    preferences: list[str] = []
    radius: float = 2.0

@app.post("/api/register")
async def register_user(user: RegisterUser):
    # Check if user exists
    existing = await users_col.find_one({"phone": user.phone})
    if existing:
        await users_col.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "fcm_token": user.fcm_token, 
                "name": user.name,
                "skills": user.skills,
                "preferences": user.preferences,
                "radius": user.radius
            }}
        )
        return {"status": "updated", "id": str(existing["_id"])}
    else:
        new_user = {
            "name": user.name,
            "phone": user.phone,
            "fcm_token": user.fcm_token,
            "points": 0,
            "badge": "Người tốt bụng",
            "skills": user.skills,
            "preferences": user.preferences,
            "radius": user.radius,
            "lat": None,
            "lng": None
        }
        res = await users_col.insert_one(new_user)
        return {"status": "created", "id": str(res.inserted_id)}

class UpdateUser(BaseModel):
    skills: str
    preferences: list[str]
    radius: float = 2.0

@app.get("/api/user/{user_id}")
async def get_user(user_id: str):
    user = await users_col.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
        return user
    raise HTTPException(status_code=404, detail="User not found")

@app.put("/api/user/{user_id}")
async def update_user(user_id: str, data: UpdateUser):
    result = await users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "skills": data.skills,
            "preferences": data.preferences,
            "radius": data.radius
        }}
    )
    if result.modified_count > 0 or result.matched_count > 0:
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="User not found")

class LocationUpdate(BaseModel):
    user_id: str
    lat: float
    lng: float

@app.post("/api/location")
async def update_location(loc: LocationUpdate):
    result = await users_col.update_one(
        {"_id": ObjectId(loc.user_id)},
        {"$set": {"lat": loc.lat, "lng": loc.lng}}
    )
    if result.modified_count > 0:
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="User not found")

class VolunteerRequest(BaseModel):
    alert_id: str
    user_id: str
    role: str

@app.post("/api/volunteer")
async def register_volunteer(req: VolunteerRequest):
    user = await users_col.find_one({"_id": ObjectId(req.user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    volunteer_data = {
        "user_id": str(user["_id"]),
        "name": user["name"],
        "phone": user.get("phone", ""),
        "role": req.role,
        "skills": user.get("skills", ""),
        "status": "en_route",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Save to local volunteer list file
    try:
        vol_file = "volunteers_list.json"
        vol_list = []
        if os.path.exists(vol_file):
            with open(vol_file, "r", encoding="utf-8") as f:
                try:
                    vol_list = json.load(f)
                except:
                    pass
        
        # Upsert by phone (or user_id)
        phone_key = volunteer_data.get("phone", volunteer_data["user_id"])
        existing_vol = next((v for v in vol_list if v.get("phone") == phone_key or v.get("user_id") == volunteer_data["user_id"]), None)
        if existing_vol:
            existing_vol.update({
                "name": volunteer_data["name"],
                "skills": volunteer_data["skills"],
                "points": user.get("points", 0),
                "badge": user.get("badge", "Người tốt bụng"),
                "last_active": volunteer_data["time"]
            })
        else:
            vol_list.append({
                "user_id": volunteer_data["user_id"],
                "phone": phone_key,
                "name": volunteer_data["name"],
                "skills": volunteer_data["skills"],
                "points": user.get("points", 0),
                "badge": user.get("badge", "Người tốt bụng"),
                "joined_at": volunteer_data["time"],
                "last_active": volunteer_data["time"]
            })
            
        with open(vol_file, "w", encoding="utf-8") as f:
            json.dump(vol_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving to volunteers_list.json: {e}")
    
    result = await alerts_col.update_one(
        {"_id": ObjectId(req.alert_id), "volunteers.user_id": {"$ne": str(user["_id"])}},
        {"$push": {"volunteers": volunteer_data}}
    )
    
    if result.modified_count > 0:
        await broadcast({"action": "volunteer_added", "alert_id": req.alert_id, "volunteer": volunteer_data})
        return {"status": "ok"}
    else:
        alert = await alerts_col.find_one({"_id": ObjectId(req.alert_id)})
        if alert and any(v.get("user_id") == str(user["_id"]) for v in alert.get("volunteers", [])):
            return {"status": "ok", "message": "Already registered"}
    raise HTTPException(status_code=404, detail="Alert not found")

@app.get("/api/alerts/{alert_id}/tracking")
async def get_alert_tracking(alert_id: str):
    alert = await alerts_col.find_one({"_id": ObjectId(alert_id)})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    volunteers = alert.get("volunteers", [])
    if not volunteers:
        return []
        
    user_ids = [ObjectId(v["user_id"]) for v in volunteers]
    users = await users_col.find({"_id": {"$in": user_ids}}).to_list(length=None)
    
    tracking_data = []
    for v in volunteers:
        # Find matching user to get latest lat/lng
        user_info = next((u for u in users if str(u["_id"]) == v["user_id"]), None)
        if user_info:
            tracking_data.append({
                "user_id": v["user_id"],
                "name": v["name"],
                "phone": user_info.get("phone", v.get("phone", "")),
                "role": v["role"],
                "skills": v["skills"],
                "status": v.get("status", "en_route"),
                "lat": user_info.get("lat"),
                "lng": user_info.get("lng")
            })
    alert["_id"] = str(alert["_id"])
    return {
        "alert": alert,
        "tracking": tracking_data
    }

@app.post("/api/alerts/{alert_id}/false_alarm")
async def report_false_alarm(alert_id: str):
    result = await alerts_col.update_one(
        {"_id": ObjectId(alert_id)},
        {"$inc": {"false_alarm_reports": 1}}
    )
    if result.modified_count > 0:
        await broadcast({"action": "update", "id": alert_id, "false_alarm": True})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

class VolunteerStatusUpdate(BaseModel):
    status: str

def get_badge_from_points(points: int):
    if points < 100: return "Người tốt bụng"
    elif points < 200: return "Tân hiệp sĩ"
    elif points < 300: return "Hiệp Sĩ Tập Sự"
    elif points < 400: return "Hiệp Sĩ Đường Phố"
    elif points < 500: return "Anh Hùng Cứu Nạn"
    return "Huyền Thoại nhân ái"

@app.post("/api/alerts/{alert_id}/volunteer/{user_id}/status")
async def update_volunteer_status(alert_id: str, user_id: str, status_update: VolunteerStatusUpdate):
    status = status_update.status
    
    alert = await alerts_col.find_one({"_id": ObjectId(alert_id)})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    prev_status = None
    for v in alert.get("volunteers", []):
        if v.get("user_id") == user_id:
            prev_status = v.get("status")
            break
            
    if prev_status == status:
        return {"status": "ok"}
    
    result = await alerts_col.update_one(
        {"_id": ObjectId(alert_id), "volunteers.user_id": user_id},
        {"$set": {"volunteers.$.status": status}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert or Volunteer not found")
        
    await broadcast({
        "action": "volunteer_status_changed", 
        "alert_id": alert_id, 
        "user_id": user_id, 
        "status": status
    })
    
    # Points are now only awarded in close_alert to prevent double counting.
    if status == "false_alarm":
        await alerts_col.update_one(
            {"_id": ObjectId(alert_id)},
            {"$inc": {"false_alarm_reports": 1}}
        )
        await broadcast({"action": "update", "id": alert_id, "false_alarm": True})
        
    return {"status": "ok"}

# =====================
# MANUAL TRIGGER ENDPOINTS
# =====================
@app.post("/trigger/{cam_id}/{alert_type}")
async def trigger_manual(cam_id: str, alert_type: str):
    if alert_type not in ["fire", "accident", "congestion"]:
        raise HTTPException(status_code=400, detail="Invalid alert type")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger/{cam_id}",
                json={"alert_type": alert_type},
                timeout=5.0
            )
            return {"status": "triggered", "type": alert_type, "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger alert: {str(e)}")

@app.post("/trigger/{alert_type}")
async def trigger_manual_legacy(alert_type: str):
    if alert_type not in ["fire", "accident", "congestion"]:
        raise HTTPException(status_code=400, detail="Invalid alert type")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger/cam01",
                json={"alert_type": alert_type},
                timeout=5.0
            )
            return {"status": "triggered", "type": alert_type, "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger alert: {str(e)}")

# =====================
# HEALTH CHECK
# =====================
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Arlert_BE", "time": datetime.now().isoformat()}