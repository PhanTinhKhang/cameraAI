# System Technical Documentation

## 1. Component Overview
The system consists of three main running components:
- **ML Camera Service** (`ML/arlert.py`): Runs YOLO models on a video stream, records video clips using `ffmpeg`, and hosts WebRTC/MJPEG endpoints.
- **Backend API** (`Arlert_BE/alert_server.py`): A FastAPI application handling MongoDB operations, WebSockets, Firebase Push Notifications, and Google Maps Directions API distance calculations.
- **Mobile/Web Frontends**: 
  - `ai-cam-web`: React app for the admin dashboard.
  - `flutter_app`: Mobile application for volunteers.

## 2. Workflows and Communication

### A. Detection and Incident Creation
1. **Multi-Camera Inference**: `arlert.py` runs a central `CameraManager` that performs batch inference across multiple RTSP streams simultaneously. It uses three YOLO models (`ver3.pt` for accidents, `fire.pt` for fires, `person.pt` for vehicles).
2. **Buffering**: It maintains a continuous rolling frame buffer (5 seconds of `PRE_EVENT_SEC`). 
3. **Trigger**: If a detection meets the frame threshold or stationary time threshold, it triggers recording for `POST_EVENT_SEC` (5 seconds). *Note: The detection frame counters are strictly bounded (`max_counter = ALERT_FRAME_THRESHOLD + 20`) to prevent infinite growth, ensuring the system resets and is ready for subsequent alerts within ~2 seconds of an incident leaving the frame.*
4. **Saving**: Independent `EventRecorder` instances for each camera use `subprocess.Popen` to call `ffmpeg`, encoding the 10-second clip (h264_nvenc or libx264) to an `.mp4` file isolated by camera ID.
5. **API Call**: `arlert.py` sends a `POST` request to `http://localhost:8000/alert` containing the file path, metadata, and the specific `cam_id` that triggered the alert.

### B. Alert Dispatch and Notifications
1. **Database Save**: `alert_server.py` receives the alert, adds fields like `status="open"`, and saves it to MongoDB (`alerts_col`).
2. **WebSocket Broadcast**: The backend immediately broadcasts the new alert JSON to all connected React clients via `/ws/alerts`.
3. **Distance Calculation**: The backend queries `users_col` for all users with FCM tokens. It calculates the road distance between the camera's GPS and the user's GPS using the open-source OSRM API (falling back to a local Haversine formula calculation if the API fails). A 60-second coordinate cache is used to prevent OSRM rate-limiting for users in identical locations.
4. **Filtering**: If the calculated distance is less than or equal to the user's customized `radius` (from their profile settings), and the alert type matches their preferences, they are selected for dispatch.
5. **FCM Push**: The backend uses the `firebase_admin` SDK to send a message. The payload is 100% data (`is_data_notification: "true"`), containing no standard FCM "notification" block. The entire dispatch loop is wrapped in per-user `try/except` blocks to guarantee that a failure (like a malformed token) won't crash the loop and skip other users.
6. **Mobile Handling**: The Flutter app's background isolate (`_firebaseMessagingBackgroundHandler`) receives the data payload and manually generates a system notification using the `flutter_local_notifications` plugin, utilizing `priority=high` to wake devices.

### C. Live Video Streaming
1. **WebRTC Proxy**: When a volunteer wants to view the live camera, the Flutter app sends an SDP offer to `alert_server.py` (`POST /offer/{cam_id}`).
2. **Relay**: The backend proxies this request to `arlert.py` (`http://localhost:8080/offer/{cam_id}`).
3. **P2P Connection**: `arlert.py` processes the SDP offer using the `aiortc` library, generates an answer, and streams the video frames directly to the Flutter app via WebRTC.
4. **MJPEG Fallback**: If the WebRTC connection fails (e.g., `RTCPeerConnectionStateFailed`), the Flutter app falls back to a standard HTTP MJPEG stream at `http://<host>:8080/mjpeg/{cam_id}`.

### D. Volunteer Response and Routing
1. **Registration**: When a user taps the notification, Flutter sends a `POST /api/volunteer` request. The backend adds the user to the alert's `volunteers` array in MongoDB.
2. **Routing**: The Flutter app calculates the driving route to the incident. *Note: Unlike the backend which uses Google Maps API for distance, the mobile app fetches route polylines using the open-source OSRM routing API.*
3. **Live Tracking**: As the volunteer moves, the Flutter app sends `POST /api/location`. The React dashboard polls `/api/alerts/{id}/tracking` to live-update the map markers.
4. **Completion**: When the user finishes, they send a status update. If `status="completed"`, the backend updates their profile in MongoDB, adding +25 points and updating their badge title.
5. **Force Dispatch Visibility**: The mission screen dynamically displays a banner informing the volunteer of which emergency forces (e.g., Police 113, Fire 114) have already been dispatched by the admin, providing real-time situational awareness.
6. **Mobile Media Chat**: Volunteers can communicate with the central admin via a dedicated chat interface supporting text, audio recording, and photo uploads. Once the incident is marked as closed by the admin, this chat interface is locked to a read-only mode to preserve the archive without allowing further messages.

### E. Admin Dashboard Operations
1. **Dynamic Camera Settings**: Admins can add, edit, or delete IP cameras dynamically via a configuration modal. `arlert.py` polls this configuration and restarts camera capture threads on-the-fly if an RTSP URL changes.
2. **Alert History**: The React UI fetches an uncapped history of all alerts (`limit=0`), but applies a strict client-side date filter defaulting to **today's date** to prevent UI clutter.
3. **Audio Unlocking**: Browser security prevents autoplaying alarm sounds (`alert.mp3`). The dashboard features a global DOM listener (`unlockAudio`) that silently activates audio permissions the moment an admin clicks anywhere on the page, paired with a visual banner prompting interaction.
4. **Emergency Dispatch Integration**: The dashboard provides three distinct, reactive buttons for dispatching specialized forces (Police 113, Fire 114, Medical 115). Clicking these buttons updates the backend and visually disables the button across all clients in real-time, displaying a dynamic tracking banner (e.g. "Đã báo: 113, 115").
5. **Consolidated Focus Panel**: Admins can open a unified "Chế độ theo dõi" (Focus Panel) for any active or closed alert. This panel displays a live WebRTC camera feed (or an `.mp4` video playback if the alert is closed), a Google Map plotting real-time volunteer GPS coordinates, and a list of tracking data including volunteer roles, skills, and **contact phone numbers** (pulled dynamically from `users_col`). 
6. **Interactive Media Chat**: Admins can communicate with dispatched volunteers via a real-time chat box inside the Focus Panel. It supports text, uploading images, and live audio recording via `MediaRecorder`. When an alert is closed, the chat archive becomes strictly read-only for transparency, preventing new messages from being sent.



### F. Recent Refinements & Bug Fixes (Phase 5)
1. **Chat UI/UX Enhancements**:
   - Fixed media rendering in the mobile app so admin-uploaded images are visible (using `ApiService.cachedDomain` injection).
   - Enabled audio playback in the mobile app for admin-sent voice notes.
   - Made the Chat Floating Action Button draggable to avoid obstructing the Google Map interface, and dynamically adjusted its default `Y` coordinate to safely hover above the dense bottom action panel (`Xem Camera` / `Báo Cáo`).
2. **Notification & Audio Feedback**:
   - Added Messenger-style audio alerts (`messenger.mp3`) to the React dashboard for incoming messages and new volunteer joins.
   - Added in-app local notifications (audio/vibration) for the Flutter app when a chat message arrives while the chat box is closed. The notification body now displays an actual preview of the message (text snippet, `[Hình ảnh]`, or `[Tin nhắn thoại]`).
   - Refactored the siren alarm logic (`alarm_clock.ogg`) in the Flutter app to strictly respect active zones, ensuring it only plays when a real-time incident actually falls within the user's customized `preferredRadius`.
3. **Map Rendering & State Synchronization**:
   - Fixed a critical Flutter `GoogleMap` state bug where map markers and circles failed to update instantly due to Set reference caching (`Set.from()`).
   - Cleaned up the mission screen by removing redundant user markers.
   - Implemented a collapsed UI for the active alerts banner in the mobile app to ensure the map remains usable during mass-casualty or multi-alert scenarios.
   - Refactored the FCM background tap handler to present volunteers with an `AlertBottomSheet` preview of the incident instead of auto-accepting the mission by forcing them into the `MissionScreen`.
4. **Stability, Boot Flow, & Data Accuracy Updates**:
   - **MapScreen Fast Boot (Unblocked Async)**: Heavily optimized the mobile app boot flow by decoupling GPS, API polling, and WebSocket instantiation from `Future.wait()`. The app now boots to the interactive map instantly rather than freezing for up to 10 seconds waiting for GPS hardware locks.
   - **Terminated App Push Notifications**: Integrated `getNotificationAppLaunchDetails` to reliably capture completely terminated-state push notifications triggered via local data payloads, fixing silent drops. Added `ModalRoute` listeners to guarantee bottom sheets wait for route animations to finish before attempting to mount.
   - **Strict OSRM Routing Override**: Completely deprecated the straight-line Haversine fallback in the mobile app. All distance calculations are now strictly enforced using real-road distances via OSRM to ensure accurate dispatch radii. If the road distance exceeds the `preferredRadius`, the system strictly filters out the alert, eliminating false-positives for nearby (but unreachable) incidents.
   - **ValueNotifier State Corruption Fix**: Resolved a critical Flutter crash where tapping subsequent push notifications resulted in unresponsive UI elements ("panel not showing on next alert"). The fix implements an `addPostFrameCallback` boundary that prevents synchronous modification of `ValueNotifier` during listener execution loops.
   - **Map State Rehydration**: Replaced static tabs in the Flutter app with an interactive reload trigger. Tapping the active "Map" tab immediately triggers a global state refresh, re-pinging GPS and fetching the latest camera coordinates.
   - **React WebSocket Cleanup**: Hardened the `useAlerts.js` socket component to rigorously clean up duplicate WS connections spawned by React Strict Mode, stopping duplicate alert sounds and excessive network load.
