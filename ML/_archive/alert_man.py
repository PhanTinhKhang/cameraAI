import cv2
import asyncio
import torch
import time
import datetime
import threading
import os
import requests
from collections import deque
import subprocess

from ultralytics import YOLO
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
    RTCConfiguration,
    RTCIceServer
)
from aiohttp import web
import aiohttp_cors
import av

# =========================
# CONFIG
# =========================
RTSP_URL = 0
CAM_ID = "cam01"
CAM_LOCATION = "Ngã tư Nguyễn Trãi - CMT8"

ALERT_VIDEO_DIR = "../alerts"
os.makedirs(ALERT_VIDEO_DIR, exist_ok=True)

ALERT_FRAME_THRESHOLD = 3
VEHICLE_COUNT_THRESHOLD = 10
VEHICLE_STATIONARY_TIME = 60
ALERT_COOLDOWN = {
    "accident": 3600,
    "fire": 3600,
    "congestion": 3600
}
PRE_EVENT_SEC = 4
POST_EVENT_SEC = 5

TARGET_FPS = 25

device = "cuda" if torch.cuda.is_available() else "cpu"

# =========================
# MODELS
# =========================
model_accident = YOLO("ver2OkWithFireAndAccident.pt").to(device)
model_fire = YOLO("fire.pt").to(device)
model_vehicle = YOLO("person.pt").to(device)

# =========================
# GLOBAL FRAME
# =========================
latest_frame = None
frame_lock = threading.Lock()

# =========================
# MANUAL TRIGGER FLAG
# =========================
manual_trigger_queue = []
trigger_lock = threading.Lock()

# =========================
# CAMERA THREAD
# =========================
def camera_loop():
    global latest_frame
    cap = cv2.VideoCapture(RTSP_URL)

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        with frame_lock:
            latest_frame = frame.copy()

threading.Thread(target=camera_loop, daemon=True).start()

# =========================
# ALERT STATE
# =========================
last_alert_time = {"accident": 0, "fire": 0, "congestion": 0}
acc_counter = fire_counter = 0
tracked_vehicles = {}

# =========================
# EVENT RECORDER
# =========================
class EventRecorder:
    def __init__(self, alert_type):
        self.alert_type = alert_type
        self.buffer = deque()
        self.recording = False
        self.post_left = 0

    def start(self, pre_frames):
        if self.recording:
            return
        self.recording = True
        self.post_left = int(POST_EVENT_SEC * TARGET_FPS)
        self.buffer = deque(pre_frames)
        print(f"🎬 Started recording {self.alert_type}")

    def push(self, frame):
        if not self.recording:
            return
        self.buffer.append(frame)
        self.post_left -= 1
        if self.post_left <= 0:
            self.save()

    def save(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{ALERT_VIDEO_DIR}/{CAM_ID}_{self.alert_type}_{ts}.mp4"

        h, w, _ = self.buffer[0].shape

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{w}x{h}",
            "-r", str(TARGET_FPS),
            "-i", "-",
            "-an",
            "-c:v", "h264_nvenc",
            "-preset", "fast",
            "-r", str(TARGET_FPS),
            "-g", "50",
            "-profile:v", "baseline",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            path
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        for f in self.buffer:
            proc.stdin.write(f.tobytes())

        proc.stdin.close()
        proc.wait()

        print(f"💾 Saved video: {path}")

        requests.post("http://localhost:8000/alert", json={
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "location": CAM_LOCATION,
            "type": self.alert_type,
            "video": path,
            "stream": RTSP_URL
        })

        self.recording = False
        self.buffer.clear()

fire_rec = EventRecorder("fire")
acc_rec = EventRecorder("accident")
congestion_rec = EventRecorder("congestion")

# =========================
# YOLO + ALERT LOOP
# =========================
def detection_loop():
    global acc_counter, fire_counter, tracked_vehicles

    pre_buffer = deque(maxlen=int(PRE_EVENT_SEC * TARGET_FPS))
    
    frame_time = 1.0 / TARGET_FPS
    last_frame_time = time.time()

    while True:
        loop_start = time.time()
        
        if latest_frame is None:
            time.sleep(0.01)
            continue

        with frame_lock:
            frame = latest_frame.copy()

        pre_buffer.append(frame)

        # Check manual triggers
        with trigger_lock:
            if manual_trigger_queue:
                alert_type = manual_trigger_queue.pop(0)
                now = time.time()
                
                print(f"🔔 Manual trigger received: {alert_type}")
                
                # Force trigger regardless of cooldown
                if alert_type == "fire":
                    last_alert_time["fire"] = now
                    fire_rec.start(pre_buffer)
                elif alert_type == "accident":
                    last_alert_time["accident"] = now
                    acc_rec.start(pre_buffer)
                elif alert_type == "congestion":
                    last_alert_time["congestion"] = now
                    congestion_rec.start(pre_buffer)

        # Normal detection logic
        acc = model_accident(frame, classes=[0], conf=0.4, verbose=False)
        fire1 = model_accident(frame, classes=[1], conf=0.4, verbose=False)
        fire = model_fire(frame, conf=0.4, verbose=False)
        vehicles = model_vehicle.track(frame, classes=[2, 3, 5, 7], conf=0.4, verbose=False, persist=True)

        acc_counter = acc_counter + 1 if len(acc[0].boxes) else 0
        if len(fire1[0].boxes) != 0:
            fire_counter = fire_counter + 1
        else:
            fire_counter = fire_counter + 1 if len(fire[0].boxes) else 0

        now = time.time()

        # Track individual vehicles
        current_track_ids = set()
        vehicle_count = 0
        
        if vehicles[0].boxes.id is not None:
            vehicle_count = len(vehicles[0].boxes)
            
            if vehicle_count >= VEHICLE_COUNT_THRESHOLD:
                for box in vehicles[0].boxes:
                    track_id = int(box.id)
                    current_track_ids.add(track_id)
                    
                    if track_id not in tracked_vehicles:
                        tracked_vehicles[track_id] = now
                    else:
                        duration = now - tracked_vehicles[track_id]
                        
                        if duration >= VEHICLE_STATIONARY_TIME:
                            if now - last_alert_time["congestion"] > ALERT_COOLDOWN["congestion"]:
                                last_alert_time["congestion"] = now
                                congestion_rec.start(pre_buffer)
                                tracked_vehicles[track_id] = now
            else:
                tracked_vehicles.clear()
        
        tracked_vehicles = {tid: start_time for tid, start_time in tracked_vehicles.items() if tid in current_track_ids}

        if fire_counter >= ALERT_FRAME_THRESHOLD and now - last_alert_time["fire"] > ALERT_COOLDOWN["fire"]:
            last_alert_time["fire"] = now
            fire_rec.start(pre_buffer)

        if acc_counter >= ALERT_FRAME_THRESHOLD and now - last_alert_time["accident"] > ALERT_COOLDOWN["accident"]:
            last_alert_time["accident"] = now
            acc_rec.start(pre_buffer)

        fire_rec.push(frame)
        acc_rec.push(frame)
        congestion_rec.push(frame)

        processing_time = time.time() - loop_start
        sleep_time = frame_time - processing_time
        
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        actual_frame_time = time.time() - last_frame_time
        if actual_frame_time > frame_time * 1.5:
            print(f"Warning: Processing slower than {TARGET_FPS}fps. Actual: {1/actual_frame_time:.1f}fps")
        
        last_frame_time = time.time()

threading.Thread(target=detection_loop, daemon=True).start()

# =========================
# WEBRTC
# =========================
class WebRTCCamera(VideoStreamTrack):
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        while latest_frame is None:
            await asyncio.sleep(0.01)

        with frame_lock:
            frame = latest_frame.copy()

        video = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video.pts = pts
        video.time_base = time_base
        return video

async def offer(request):
    params = await request.json()
    pc = RTCPeerConnection(
        RTCConfiguration([RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    )
    pc.addTrack(WebRTCCamera())

    await pc.setRemoteDescription(
        RTCSessionDescription(params["sdp"], params["type"])
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

# =========================
# MANUAL TRIGGER ENDPOINT
# =========================
async def manual_trigger(request):
    """Receive manual trigger from alert_server"""
    try:
        params = await request.json()
        alert_type = params.get("alert_type")
        
        if alert_type not in ["fire", "accident", "congestion"]:
            return web.json_response({
                "status": "error",
                "message": "Invalid alert type"
            }, status=400)
        
        with trigger_lock:
            manual_trigger_queue.append(alert_type)
        
        print(f"✅ Manual trigger queued: {alert_type}")
        
        return web.json_response({
            "status": "ok",
            "message": f"Manual {alert_type} alert triggered"
        })
    except Exception as e:
        return web.json_response({
            "status": "error",
            "message": str(e)
        }, status=500)

# =========================
# HTTP SERVER
# =========================
app = web.Application()
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_headers="*",
        allow_methods="*",
        allow_credentials=True
    )
})

# WebRTC offer endpoint
resource = cors.add(app.router.add_resource("/offer"))
cors.add(resource.add_route("POST", offer))

# Manual trigger endpoint
trigger_resource = cors.add(app.router.add_resource("/manual_trigger"))
cors.add(trigger_resource.add_route("POST", manual_trigger))

web.run_app(app, port=8080)