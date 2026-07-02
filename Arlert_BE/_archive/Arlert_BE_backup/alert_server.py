# =====================
# alert_server.py
# =====================
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import json
import os
import httpx

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
# STATIC VIDEO
# =====================
app.mount(
    "/videos",
    StaticFiles(directory=VIDEO_DIR),
    name="videos"
)

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
            await ws.send_text(json.dumps(alert_copy))
        except:
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
    alert["false_alarm_reports"] = 0

    # Inject latest camera config (name, lat, lng)
    config = await config_col.find_one({"type": "cameras"})
    if config and "cameras" in config and len(config["cameras"]) > 0:
        cam_config = config["cameras"][0]
        alert["location"] = cam_config.get("name", alert.get("location"))
        alert["lat"] = cam_config.get("lat")
        alert["lng"] = cam_config.get("lng")
        alert["stream"] = cam_config.get("stream", alert.get("stream"))

    # save DB
    result = await alerts_col.insert_one(alert)
    alert["_id"] = str(result.inserted_id)
    alert["time"] = alert["time"].strftime("%Y-%m-%d %H:%M:%S")

    # broadcast realtime
    await broadcast(alert)
    
    # TODO: Trigger Firebase Push Notification here
    # (Requires distance calculation via Google Maps API first)

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
        "stream": "http://localhost:8080/offer",
        "lat": 16.075433810355626,
        "lng": 108.14969733956971
    }]

from typing import List

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
        await broadcast({"action": "update", "id": alert_id, "status": "closed"})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

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

# =====================
# MOBILE APP ENDPOINTS
# =====================
class RegisterUser(BaseModel):
    name: str
    phone: str
    fcm_token: str

@app.post("/api/register")
async def register_user(user: RegisterUser):
    # Check if user exists
    existing = await users_col.find_one({"phone": user.phone})
    if existing:
        await users_col.update_one(
            {"_id": existing["_id"]},
            {"$set": {"fcm_token": user.fcm_token, "name": user.name}}
        )
        return {"status": "updated", "id": str(existing["_id"])}
    else:
        new_user = {
            "name": user.name,
            "phone": user.phone,
            "fcm_token": user.fcm_token,
            "points": 0
        }
        res = await users_col.insert_one(new_user)
        return {"status": "created", "id": str(res.inserted_id)}

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
        "role": req.role,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    result = await alerts_col.update_one(
        {"_id": ObjectId(req.alert_id)},
        {"$push": {"volunteers": volunteer_data}}
    )
    
    if result.modified_count > 0:
        await broadcast({"action": "volunteer_added", "alert_id": req.alert_id, "volunteer": volunteer_data})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

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

# =====================
# MANUAL TRIGGER ENDPOINTS
# =====================
@app.post("/trigger/{alert_type}")
async def trigger_manual(alert_type: str):
    if alert_type not in ["fire", "accident", "congestion"]:
        raise HTTPException(status_code=400, detail="Invalid alert type")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger",
                json={"alert_type": alert_type},
                timeout=5.0
            )
            return {"status": "triggered", "type": alert_type, "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger alert: {str(e)}")