# Phase 2: Multi-Camera Plug-and-Play Foundation

This document outlines the architectural changes required to transform the current single-camera hardcoded system into a dynamic, multi-camera plug-and-play platform.

## User Review Required
> [!IMPORTANT]
> Please review this architecture. Refactoring `arlert.py` to support multiple cameras simultaneously requires converting global variables into object-oriented Camera Nodes. This directly affects how video is recorded and how radius alerts are calculated.

## Addressing Stability Concerns (Batching)
1. **Preventing Frame Stacking (RTSP Lag):** Every camera will have its own dedicated, lightweight Python thread (`CameraStream` class) running a rapid `cv2.VideoCapture.grab()` loop. This constantly empties the OpenCV buffer so that `self.latest_frame` is always the absolute newest frame with zero lag.
2. **Preventing Wrong Sources:** When we call `model([frame_cam1, frame_cam2])`, it strictly returns `[results_cam1, results_cam2]`. By wrapping each camera in a `CameraNode` object, the system will map `results[i]` precisely back to the specific `CameraNode` that supplied the frame. 

---

## Handling Sub-Systems Dynamically
As requested, all dependent sub-systems will be updated to be camera-aware:

* **Continuous Recording (24/7):** Each `CameraNode` will instantiate its own `ContinuousRecorder`. Videos will be saved as `../continuous_recordings/{date}/{hour}/{camera_id}_{timestamp}.mp4`.
* **Event Recording:** Each `CameraNode` will have its own `fire_rec`, `acc_rec`, and `congestion_rec` buffers. When an event happens on `cam02`, only `cam02`'s video is saved to `../alerts/cam02_accident_{timestamp}.mp4`.
* **Radius Alerts to Volunteers:** Currently, the system uses a hardcoded coordinate ("Ngã tư Hàng Xanh"). We will update `alert_server.py` so that when a specific camera triggers an alert, the backend fetches that exact camera's GPS coordinates from the `cameras_col` database and uses those coordinates to query `users_col` for nearby volunteers.

---

## Proposed Architecture

### 1. Database & Backend API (`alert_server.py`)
- **MongoDB Collection (`cameras_col`):** Store `{ camera_id, name, rtsp_url, location: { lat, lng, name }, status }`.
- **REST Endpoints:** 
  - `POST /api/cameras`: Add a new camera.
  - `GET /api/cameras`: List active cameras.
  - `DELETE /api/cameras/{camera_id}`: Remove a camera.
- **WebSocket Synchronization:** When the UI adds a camera, the backend will update MongoDB and notify `arlert.py` via HTTP to hot-load the stream.

### 2. ML Engine Refactoring (`arlert.py`)
- **`CameraNode` Class:** Encapsulates all state for a single camera.
  - Owns its `VideoCapture` thread, `EventRecorder`, and `ContinuousRecorder`.
  - Owns detection counters (`acc_counter`, `fire_counter`).
  - Owns a `WebRTCCamera` video track.
- **`CameraManager` Class:** Manages active `CameraNode`s.
  - **Inference Loop:** Iterates through active `CameraNode`s, grabs their `latest_frame`, batches them `model([f1, f2])`, and maps results back.
- **WebRTC Router:** The `aiohttp` server will use `/offer/{camera_id}` and `/mjpeg/{camera_id}` to ensure the correct video is streamed.

### 3. Admin Dashboard (`ai-cam-web`)
- **Camera Management UI:** Add a "Cameras" tab to add an RTSP URL and GPS coordinates.
- **Dynamic Map:** The Map will fetch `GET /api/cameras` and render multiple markers. Clicking a marker will change the `camera_id` prop passed to `WebRTCPlayer.jsx`.

---

## Verification Plan
1. **Multi-Camera WebRTC Test:** Add two cameras. Switch between their markers on the Map. Verify the WebRTC feed correctly transitions between the different RTSP sources.
2. **Dynamic Recording Test:** Manually trigger an accident on `cam02`. Verify the saved video is correctly labeled `cam02` and `cam01` continues recording normally.
3. **Radius Alert Test:** Trigger an alert on a camera. Verify the push notification sent to the mobile app uses the precise GPS coordinates of that specific camera, rather than the hardcoded default.
