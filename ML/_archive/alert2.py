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
RTSP_URL = "aaaaaaaaaaaaaaaa.mp4"
CAM_ID = "cam01"
CAM_LOCATION = "Ngã tư Nguyễn Trãi - CMT8"

ALERT_VIDEO_DIR = "../alerts"
os.makedirs(ALERT_VIDEO_DIR, exist_ok=True)

ALERT_FRAME_THRESHOLD = 3
VEHICLE_STATIONARY_TIME = 60  # Vehicle must be stationary for 60 seconds
MOVEMENT_THRESHOLD = 30  # Pixels - if vehicle moves less than this, consider stationary
ALERT_COOLDOWN = {
    "accident": 3600,
    "fire": 3600,
    "congestion": 3600
}
PRE_EVENT_SEC = 4
POST_EVENT_SEC = 5

device = "cuda" if torch.cuda.is_available() else "cpu"

# =========================
# MODELS
# =========================
model_accident = YOLO("best.pt").to(device)
model_fire = YOLO("fire.pt").to(device)
model_vehicle = YOLO("person.pt").to(device)

# =========================
# GLOBAL FRAME
# =========================
latest_frame = None
frame_lock = threading.Lock()

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
tracked_vehicles = {}  # {track_id: {"first_pos": (x,y), "first_time": timestamp}}

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
        self.post_left = int(POST_EVENT_SEC * 25)
        self.buffer = deque(pre_frames)

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
            "-r", "25",
            "-i", "-",
            "-an",
            "-c:v", "h264_nvenc",
            "-profile:v", "baseline",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            path
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

        for f in self.buffer:
            proc.stdin.write(f.tobytes())

        proc.stdin.close()
        proc.wait()

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

    pre_buffer = deque(maxlen=int(PRE_EVENT_SEC * 25))

    while True:
        if latest_frame is None:
            time.sleep(0.01)
            continue

        with frame_lock:
            frame = latest_frame.copy()

        pre_buffer.append(frame)

        acc = model_accident(frame, classes=[0], conf=0.8, verbose=False)
        fire = model_fire(frame, conf=0.4, verbose=False)
        # Use tracking mode to get persistent IDs for each vehicle
        vehicles = model_vehicle.track(frame, classes=[2, 3, 5, 7], conf=0.4, verbose=False, persist=True)

        acc_counter = acc_counter + 1 if len(acc[0].boxes) else 0
        fire_counter = fire_counter + 1 if len(fire[0].boxes) else 0

        now = time.time()

        # Track individual vehicles
        current_track_ids = set()
        
        if vehicles[0].boxes.id is not None:
            for box in vehicles[0].boxes:
                track_id = int(box.id)
                current_track_ids.add(track_id)
                
                # Get center position of vehicle
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                if track_id not in tracked_vehicles:
                    # New vehicle detected
                    tracked_vehicles[track_id] = {
                        "first_pos": (center_x, center_y),
                        "first_time": now
                    }
                else:
                    # Check if vehicle has been stationary
                    first_pos = tracked_vehicles[track_id]["first_pos"]
                    first_time = tracked_vehicles[track_id]["first_time"]
                    
                    # Calculate distance moved
                    distance = ((center_x - first_pos[0])**2 + (center_y - first_pos[1])**2)**0.5
                    
                    if distance > MOVEMENT_THRESHOLD:
                        # Vehicle moved significantly, reset tracking
                        tracked_vehicles[track_id] = {
                            "first_pos": (center_x, center_y),
                            "first_time": now
                        }
                    elif (now - first_time) >= VEHICLE_STATIONARY_TIME:
                        # Vehicle has been stationary for over 60 seconds!
                        if now - last_alert_time["congestion"] > ALERT_COOLDOWN["congestion"]:
                            last_alert_time["congestion"] = now
                            congestion_rec.start(pre_buffer)
                            # Reset this vehicle's tracking after alert
                            tracked_vehicles[track_id]["first_time"] = now
        
        # Remove vehicles that are no longer in frame
        tracked_vehicles = {tid: data for tid, data in tracked_vehicles.items() if tid in current_track_ids}

        if fire_counter >= ALERT_FRAME_THRESHOLD and now - last_alert_time["fire"] > ALERT_COOLDOWN["fire"]:
            last_alert_time["fire"] = now
            fire_rec.start(pre_buffer)

        if acc_counter >= ALERT_FRAME_THRESHOLD and now - last_alert_time["accident"] > ALERT_COOLDOWN["accident"]:
            last_alert_time["accident"] = now
            acc_rec.start(pre_buffer)

        fire_rec.push(frame)
        acc_rec.push(frame)
        congestion_rec.push(frame)

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

resource = cors.add(app.router.add_resource("/offer"))
cors.add(resource.add_route("POST", offer))

web.run_app(app, port=8080)