# =====================
# alert_server.py
# =====================
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import httpx

from db import alerts_col

# =====================
# APP
# =====================
app = FastAPI()

# =====================
# PATH CONFIG (🔥 QUAN TRỌNG)
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
# STATIC VIDEO (🔥 FIX 206 / RESET)
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

# =====================
# BROADCAST
# =====================
async def broadcast(alert: dict):
    dead = []
    for ws in clients:
        try:
            await ws.send_text(json.dumps(alert))
        except:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)

# =====================
# POST ALERT
# =====================
@app.post("/alert")
async def receive_alert(alert: dict):
    """
    alert = {
      time,
      location,
      type,
      video,   # alerts/xxx.mp4
      stream
    }
    """

    # parse time
    if isinstance(alert.get("time"), str):
        alert["time"] = datetime.strptime(
            alert["time"], "%Y-%m-%d %H:%M:%S"
        )

    # lấy filename
    filename = os.path.basename(alert["video"])

    # tạo URL cho frontend
    alert["video_url"] = f"http://localhost:8000/videos/{filename}"

    # save DB
    result = await alerts_col.insert_one(alert)
    alert["_id"] = str(result.inserted_id)

    # format time lại
    alert["time"] = alert["time"].strftime("%Y-%m-%d %H:%M:%S")

    # broadcast realtime
    await broadcast(alert)

    print("🚨 ALERT SAVED:", alert["type"])
    return {"status": "ok", "video_url": alert["video_url"]}

# =====================
# GET ALERT HISTORY
# =====================
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
# MANUAL TRIGGER ENDPOINTS
# =====================
@app.post("/trigger/fire")
async def trigger_fire():
    """Trigger manual fire alert"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger",
                json={"alert_type": "fire"},
                timeout=5.0
            )
            return {"status": "triggered", "type": "fire", "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger fire alert: {str(e)}")

@app.post("/trigger/accident")
async def trigger_accident():
    """Trigger manual accident alert"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger",
                json={"alert_type": "accident"},
                timeout=5.0
            )
            return {"status": "triggered", "type": "accident", "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger accident alert: {str(e)}")

@app.post("/trigger/congestion")
async def trigger_congestion():
    """Trigger manual congestion alert"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ARLERT_SERVICE_URL}/manual_trigger",
                json={"alert_type": "congestion"},
                timeout=5.0
            )
            return {"status": "triggered", "type": "congestion", "response": response.json()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger congestion alert: {str(e)}")