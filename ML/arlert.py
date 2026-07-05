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
import numpy as np
import os

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
os.environ["OPENCV_FFMPEG_READ_TIMEOUT"] = "3000"

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
import sys

# Windows asyncio bug workaround for ConnectionResetError
if sys.platform == 'win32':
    import functools
    from asyncio.proactor_events import _ProactorBasePipeTransport
    def silence_connection_reset(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except ConnectionResetError:
                pass
        return wrapper
    _ProactorBasePipeTransport._call_connection_lost = silence_connection_reset(_ProactorBasePipeTransport._call_connection_lost)

# =========================
# CONFIG
# =========================
ALERT_VIDEO_DIR = "../alerts"
CONTINUOUS_VIDEO_DIR = "../continuous_recordings"
os.makedirs(ALERT_VIDEO_DIR, exist_ok=True)
os.makedirs(CONTINUOUS_VIDEO_DIR, exist_ok=True)

ALERT_FRAME_THRESHOLD = 3
VEHICLE_COUNT_THRESHOLD = 7
VEHICLE_STATIONARY_TIME = 10
ALERT_COOLDOWN = {"accident": 20, "fire": 20, "congestion": 30}
PRE_EVENT_SEC = 5
POST_EVENT_SEC = 5
TARGET_FPS = 20
CONTINUOUS_CLIP_DURATION = 20

print(torch.cuda.is_available())
device = "cuda" if torch.cuda.is_available() else "cpu"
ffmpeg_codec = "h264_nvenc" if torch.cuda.is_available() else "libx264"

model_accident = YOLO("ver3.pt").to(device)
model_fire = YOLO("fire.pt").to(device)
model_vehicle = YOLO("person.pt").to(device)

# =========================
# CAMERA NODE CLASS
# =========================
class CameraNode:
    def __init__(self, cam_id, name, rtsp_url, lat, lng):
        self.cam_id = cam_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.lat = lat
        self.lng = lng
        
        self.latest_frame = None
        self.frame_lock = threading.Lock()
        self.is_running = True
        
        self.last_alert_time = {"accident": 0, "fire": 0, "congestion": 0}
        self.is_active = {"accident": False, "fire": False, "congestion": False}
        self.acc_counter = 0
        self.fire_counter = 0
        self.tracked_vehicles = {}
        
        self.global_pre_buffer = deque(maxlen=int(PRE_EVENT_SEC * TARGET_FPS))
        self.record_lock = threading.Lock()
        
        self.fire_rec = EventRecorder("fire", self)
        self.acc_rec = EventRecorder("accident", self)
        self.congestion_rec = EventRecorder("congestion", self)
        self.continuous_rec = ContinuousRecorder(self)
        
        self.manual_trigger_queue = []
        self.trigger_lock = threading.Lock()
        
        threading.Thread(target=self.camera_loop, daemon=True).start()
        threading.Thread(target=self.recording_loop, daemon=True).start()

    def camera_loop(self):
        def init_cap():
            try:
                url = int(self.rtsp_url)
                c = cv2.VideoCapture(url, cv2.CAP_DSHOW)
                is_live = True
            except ValueError:
                c = cv2.VideoCapture(self.rtsp_url)
                is_live = str(self.rtsp_url).startswith("rtsp://") or str(self.rtsp_url).startswith("http://")
            
            fps = c.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or fps > 100:
                fps = 30
            return c, is_live, 1.0 / fps

        cap, is_live, frame_delay = init_cap()
        fail_count = 0

        while self.is_running:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                if not is_live:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                else:
                    fail_count += 1
                    time.sleep(0.05)
                    # Reconnect if stream is dead (failed ~2.5 seconds consecutively)
                    if fail_count > 50:
                        print(f"⚠️ Reconnecting camera {self.cam_id}...")
                        cap.release()
                        time.sleep(1)
                        cap, is_live, frame_delay = init_cap()
                        fail_count = 0
                continue

            fail_count = 0
            frame = cv2.resize(frame, (640, 360))
            with self.frame_lock:
                self.latest_frame = frame.copy()
                
            if not is_live:
                elapsed = time.time() - start_t
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
        cap.release()

    def recording_loop(self):
        frame_time = 1.0 / TARGET_FPS
        while self.is_running:
            loop_start = time.time()
            if self.latest_frame is None:
                time.sleep(0.01)
                continue
                
            with self.frame_lock:
                frame = self.latest_frame.copy()
                
            with self.record_lock:
                self.global_pre_buffer.append(frame)
                self.fire_rec.push(frame)
                self.acc_rec.push(frame)
                self.congestion_rec.push(frame)
                self.continuous_rec.push(frame)
                
            elapsed = time.time() - loop_start
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)

    def trigger_manual(self, alert_type):
        with self.trigger_lock:
            self.manual_trigger_queue.append(alert_type)

    def stop(self):
        self.is_running = False

# =========================
# EVENT RECORDER
# =========================
class EventRecorder:
    def __init__(self, alert_type, node: CameraNode):
        self.alert_type = alert_type
        self.node = node
        self.buffer = deque()
        self.recording = False
        self.post_left = 0

    def start(self, pre_frames):
        if self.recording:
            return
        self.recording = True
        self.post_left = int(POST_EVENT_SEC * TARGET_FPS)
        self.buffer = deque(pre_frames)
        print(f"🎬 Started recording {self.alert_type} on {self.node.cam_id}")

    def push(self, frame):
        if not self.recording:
            return
        self.buffer.append(frame)
        self.post_left -= 1
        if self.post_left <= 0:
            frames_to_save = list(self.buffer)
            self.recording = False
            self.buffer.clear()
            threading.Thread(target=self._save_video, args=(frames_to_save,), daemon=True).start()

    def _save_video(self, frames_to_save):
        if not frames_to_save:
            return
            
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{ALERT_VIDEO_DIR}/{self.node.cam_id}_{self.alert_type}_{ts}.mp4"
        
        try:
            requests.post("http://localhost:8000/alert", json={
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "location": self.node.name,
                "lat": self.node.lat,
                "lng": self.node.lng,
                "type": self.alert_type,
                "video": path,
                "stream": self.node.rtsp_url,
                "camera_id": self.node.cam_id
            })
        except Exception as e:
            print("Failed to notify backend of new alert:", e)
        
        h, w, _ = frames_to_save[0].shape
        
        try:
            cmd = [
                "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                "-r", str(TARGET_FPS), "-i", "-", "-an", "-c:v", ffmpeg_codec,
                "-preset", "fast", "-r", str(TARGET_FPS), "-g", "50",
                "-profile:v", "baseline", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for f in frames_to_save:
                proc.stdin.write(f.tobytes())
            proc.stdin.close()
            proc.wait()
            print(f"✅ Alert video saved: {path}")
        except Exception as e:
            print(f"❌ Error saving alert video: {e}")

# =========================
# CONTINUOUS RECORDER
# =========================
class ContinuousRecorder:
    def __init__(self, node: CameraNode):
        self.node = node
        self.buffer = deque()
        self.clip_frame_count = int(CONTINUOUS_CLIP_DURATION * TARGET_FPS)
        self.frame_counter = 0
        self.is_saving = False
        self.lock = threading.Lock()
        
    def push(self, frame):
        with self.lock:
            self.buffer.append(frame.copy())
            self.frame_counter += 1
            if self.frame_counter >= self.clip_frame_count:
                threading.Thread(target=self._save_clip, daemon=True).start()
                self.frame_counter = 0
            
    def _save_clip(self):
        if self.is_saving or len(self.buffer) == 0:
            return
        self.is_saving = True
        
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
        date_folder = now.strftime("%Y-%m-%d")
        hour_folder = now.strftime("%H")
        
        save_dir = os.path.join(CONTINUOUS_VIDEO_DIR, str(self.node.cam_id), date_folder, hour_folder)
        os.makedirs(save_dir, exist_ok=True)
        
        filename = f"{self.node.cam_id}_{timestamp}.mp4"
        path = os.path.join(save_dir, filename)
        
        with self.lock:
            frames_to_save = list(self.buffer)[:self.clip_frame_count]
            for _ in range(min(self.clip_frame_count, len(self.buffer))):
                self.buffer.popleft()
        
        if len(frames_to_save) == 0:
            self.is_saving = False
            return
            
        try:
            h, w, _ = frames_to_save[0].shape
            cmd = [
                "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                "-r", str(TARGET_FPS), "-i", "-", "-an", "-c:v", ffmpeg_codec,
                "-preset", "fast", "-r", str(TARGET_FPS), "-g", "50",
                "-profile:v", "baseline", "-pix_fmt", "yuv420p", "-movflags", "+faststart", path
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for frame in frames_to_save:
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            proc.wait()
        except Exception as e:
            print(f"❌ Exception in continuous recording ({self.node.cam_id}): {e}")
        finally:
            self.is_saving = False

# =========================
# CAMERA MANAGER
# =========================
cameras = {}
cameras_lock = threading.Lock()

def sync_cameras():
    # Attempt to load immediately
    while True:
        try:
            resp = requests.get("http://localhost:8000/api/config/cameras")
            if resp.status_code == 200:
                remote_cams = resp.json()
                with cameras_lock:
                    active_ids = {c.get("id") for c in remote_cams}
                    # Remove dead cameras
                    for cid in list(cameras.keys()):
                        if cid not in active_ids:
                            cameras[cid].stop()
                            del cameras[cid]
                            print(f"🗑️ Removed camera: {cid}")
                    
                    # Add new cameras or update changed cameras
                    for c in remote_cams:
                        cid = c.get("id")
                        remote_rtsp = c.get("rtsp_url", c.get("stream", 0))
                        
                        if cid in cameras:
                            if cameras[cid].rtsp_url != remote_rtsp:
                                print(f"🔄 Restarting camera {cid} due to RTSP URL change")
                                cameras[cid].stop()
                                del cameras[cid]
                        
                        if cid not in cameras:
                            cameras[cid] = CameraNode(
                                cam_id=cid,
                                name=c.get("name", "Unknown"),
                                rtsp_url=remote_rtsp,
                                lat=c.get("lat"),
                                lng=c.get("lng")
                            )
                            print(f"🎥 Added camera: {cid} ({remote_rtsp})")
        except Exception as e:
            print(f"Sync error: {e}")
            
        time.sleep(10)

threading.Thread(target=sync_cameras, daemon=True).start()

# =========================
# BATCH INFERENCE LOOP
# =========================
def detection_loop():
    while True:
        start_time = time.time()
        
        with cameras_lock:
            active_nodes = list(cameras.values())
            
        if not active_nodes:
            time.sleep(1)
            continue
            
        batch_frames = []
        batch_nodes = []
        
        for node in active_nodes:
            if node.latest_frame is not None:
                with node.frame_lock:
                    batch_frames.append(node.latest_frame.copy())
                batch_nodes.append(node)
                
        if not batch_frames:
            time.sleep(0.01)
            continue

        # Process batch
        acc_results = model_accident(batch_frames, classes=[0], conf=0.6, verbose=False)
        fire_results = model_fire(batch_frames, conf=0.8, verbose=False)
        vehicle_results = model_vehicle.track(batch_frames, classes=[2, 3, 5, 7], conf=0.4, verbose=False, persist=True)
        
        now = time.time()
        
        for i, node in enumerate(batch_nodes):
            # Process manual triggers
            with node.trigger_lock:
                if node.manual_trigger_queue:
                    alert_type = node.manual_trigger_queue.pop(0)
                    print(f"🔔 Manual trigger received: {alert_type} on {node.cam_id}")
                    with node.record_lock:
                        safe_pre_buffer = deque(node.global_pre_buffer)
                    if alert_type == "fire":
                        node.last_alert_time["fire"] = now
                        node.fire_rec.start(safe_pre_buffer)
                    elif alert_type == "accident":
                        node.last_alert_time["accident"] = now
                        node.acc_rec.start(safe_pre_buffer)
                    elif alert_type == "congestion":
                        node.last_alert_time["congestion"] = now
                        node.congestion_rec.start(safe_pre_buffer)

            # Update counters
            max_counter = ALERT_FRAME_THRESHOLD + 20
            acc = acc_results[i]
            fire = fire_results[i]
            vehicles = vehicle_results[i]
            
            if len(acc.boxes) > 0:
                node.acc_counter = min(max_counter, node.acc_counter + 1)
            else:
                node.acc_counter = max(0, node.acc_counter - 0.5)
                
            if len(fire.boxes) > 0:
                node.fire_counter = min(max_counter, node.fire_counter + 1)
            else:
                node.fire_counter = max(0, node.fire_counter - 0.5)

            if node.fire_counter <= 0:
                node.is_active["fire"] = False
            if node.acc_counter <= 0:
                node.is_active["accident"] = False

            current_track_ids = set()
            
            if node.fire_counter >= ALERT_FRAME_THRESHOLD and not node.is_active["fire"] and now - node.last_alert_time["fire"] > ALERT_COOLDOWN["fire"]:
                node.last_alert_time["fire"] = now
                node.is_active["fire"] = True
                with node.record_lock:
                    node.fire_rec.start(deque(node.global_pre_buffer))

            if node.acc_counter >= ALERT_FRAME_THRESHOLD and not node.is_active["accident"] and now - node.last_alert_time["accident"] > ALERT_COOLDOWN["accident"]:
                node.last_alert_time["accident"] = now
                node.is_active["accident"] = True
                with node.record_lock:
                    node.acc_rec.start(deque(node.global_pre_buffer))
                
            if vehicles.boxes is not None and vehicles.boxes.id is not None:
                stationary_count = 0
                for box in vehicles.boxes:
                    if box.id is None:
                        continue
                    track_id = int(box.id)
                    current_track_ids.add(track_id)
                    if track_id not in node.tracked_vehicles:
                        node.tracked_vehicles[track_id] = now
                    else:
                        duration = now - node.tracked_vehicles[track_id]
                        if duration >= VEHICLE_STATIONARY_TIME:
                            stationary_count += 1
                            
                if stationary_count >= VEHICLE_COUNT_THRESHOLD:
                    if not node.is_active["congestion"] and now - node.last_alert_time["congestion"] > ALERT_COOLDOWN["congestion"]:
                        node.last_alert_time["congestion"] = now
                        node.is_active["congestion"] = True
                        with node.record_lock:
                            node.congestion_rec.start(deque(node.global_pre_buffer))
                else:
                    node.is_active["congestion"] = False
            
            node.tracked_vehicles = {tid: start_time for tid, start_time in node.tracked_vehicles.items() if tid in current_track_ids}

threading.Thread(target=detection_loop, daemon=True).start()

# =========================
# WEBRTC & HTTP API
# =========================
class WebRTCCamera(VideoStreamTrack):
    def __init__(self, node: CameraNode):
        super().__init__()
        self.node = node

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        while self.node.latest_frame is None:
            await asyncio.sleep(0.01)

        with self.node.frame_lock:
            frame = self.node.latest_frame.copy()

        # Fix garbled WebRTC issue by enforcing standard resolution and contiguous memory
        frame = cv2.resize(frame, (640, 480))
        frame = np.ascontiguousarray(frame)

        video = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video.pts = pts
        video.time_base = time_base
        return video

pcs = set()

async def offer(request):
    cam_id = request.match_info.get('cam_id')
    with cameras_lock:
        if cam_id not in cameras:
            return web.json_response({"error": "Camera not found"}, status=404)
        node = cameras[cam_id]
        
    params = await request.json()
    pc = RTCPeerConnection(RTCConfiguration([RTCIceServer(urls=["stun:stun.l.google.com:19302"])]))
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"WebRTC Connection state: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            await pc.close()
            pcs.discard(pc)
            
    pc.addTrack(WebRTCCamera(node))

    await pc.setRemoteDescription(RTCSessionDescription(params["sdp"], params["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def mjpeg_handler(request):
    cam_id = request.match_info.get('cam_id')
    with cameras_lock:
        if cam_id not in cameras:
            return web.json_response({"error": "Camera not found"}, status=404)
        node = cameras[cam_id]

    async def generate():
        while True:
            try:
                if node.latest_frame is not None:
                    with node.frame_lock:
                        frame = node.latest_frame.copy()
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                    if ret:
                        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
                await asyncio.sleep(0.05)
            except Exception:
                break

    response = web.StreamResponse(status=200, reason='OK', headers={'Content-Type': 'multipart/x-mixed-replace;boundary=frame'})
    await response.prepare(request)
    try:
        async for chunk in generate():
            await response.write(chunk)
    except (ConnectionResetError, BrokenPipeError):
        pass
    return response

async def manual_trigger(request):
    cam_id = request.match_info.get('cam_id')
    with cameras_lock:
        if cam_id not in cameras:
            return web.json_response({"error": "Camera not found"}, status=404)
        node = cameras[cam_id]

    try:
        params = await request.json()
        alert_type = params.get("alert_type")
        if alert_type not in ["fire", "accident", "congestion"]:
            return web.json_response({"status": "error", "message": "Invalid alert type"}, status=400)
            
        node.trigger_manual(alert_type)
        return web.json_response({"status": "ok", "message": f"Manual {alert_type} alert triggered on {cam_id}"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)}, status=500)

async def snapshot_handler(request):
    cam_id = request.match_info.get('cam_id')
    with cameras_lock:
        if cam_id not in cameras:
            return web.json_response({"error": "Camera not found"}, status=404)
        node = cameras[cam_id]

    if node.latest_frame is not None:
        with node.frame_lock:
            frame = node.latest_frame.copy()
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        if ret:
            return web.Response(body=buffer.tobytes(), content_type='image/jpeg')

    return web.json_response({"error": "No frame available"}, status=500)

app = web.Application()
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(allow_headers="*", allow_methods="*", allow_credentials=True)
})

resource = cors.add(app.router.add_resource("/offer/{cam_id}"))
cors.add(resource.add_route("POST", offer))

mjpeg_resource = cors.add(app.router.add_resource("/mjpeg/{cam_id}"))
cors.add(mjpeg_resource.add_route("GET", mjpeg_handler))

snapshot_resource = cors.add(app.router.add_resource("/snapshot/{cam_id}"))
cors.add(snapshot_resource.add_route("GET", snapshot_handler))

trigger_resource = cors.add(app.router.add_resource("/manual_trigger/{cam_id}"))
cors.add(trigger_resource.add_route("POST", manual_trigger))

# Backward compatibility for old API calls assuming cam01
async def fallback_offer(request):
    request.match_info['cam_id'] = 'cam01'
    return await offer(request)

async def fallback_trigger(request):
    request.match_info['cam_id'] = 'cam01'
    return await manual_trigger(request)

fallback_offer_res = cors.add(app.router.add_resource("/offer"))
cors.add(fallback_offer_res.add_route("POST", fallback_offer))

fallback_trigger_res = cors.add(app.router.add_resource("/manual_trigger"))
cors.add(fallback_trigger_res.add_route("POST", fallback_trigger))

if __name__ == "__main__":
    web.run_app(app, port=8080)