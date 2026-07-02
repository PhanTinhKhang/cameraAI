# Camera AI System

A real-time emergency detection and dispatch system that captures video frames, runs YOLOv8 models to detect Accidents, Fires, and Congestion, streams the video locally, and serves an admin dashboard for alert management.

## ⚠️ Important Setup Instructions (For New Computers)

This repository **does not** include the large binary executable files needed to run the system (to keep the GitHub repository fast and clean). If you have just downloaded or cloned this project to a new computer, you **must download the following files manually** before running the system:

1. **ngrok.exe**
   - Download from: [ngrok.com](https://ngrok.com/download)
   - Place the `ngrok.exe` file directly in the main project folder (`cameraAI2/ngrok.exe`).

2. **mediamtx.exe** (WebRTC/RTSP Server)
   - Download from: [MediaMTX GitHub Releases](https://github.com/bluenviron/mediamtx/releases)
   - Place the `mediamtx.exe` file inside the `mediamtx/` folder (`cameraAI2/mediamtx/mediamtx.exe`).

3. **ffmpeg.exe**
   - Download from: [FFmpeg official site](https://ffmpeg.org/download.html)
   - Place the `ffmpeg.exe` file inside the `ML/` folder (`cameraAI2/ML/ffmpeg.exe`).

---

## 🚀 How to Run the System

Once you have placed the `.exe` files in their correct folders, you can start the entire system with a single click!

Simply double-click the `start.bat` file in the main folder.

This script will automatically open multiple terminal windows and start the following components:
- **FastAPI Alert Server**: The backend database connector and API.
- **AI Camera**: The ML service that captures video and detects emergencies.
- **Web UI**: The React/Vite admin dashboard frontend.
- **Cleaning Service**: Background cleanup routines.
- **Ngrok Tunnel**: Exposes the local server to the internet for push notifications and remote access.

## 🏗️ Architecture Overview

The ecosystem contains four main components:
1. **ML Service (`ML/`)**: A Python script (`arlert.py`) that captures frames, runs YOLOv8 models, streams video via WebRTC (port `8080`), and records incident clips.
2. **Backend Server (`Arlert_BE/`)**: A FastAPI app running on port `8000`. Connects to MongoDB, stores alerts, serves videos, and handles Firebase Push Notifications.
3. **Admin Dashboard (`ai-cam-web/`)**: A React/Vite web application running on port `5173`. Receives WebSockets, plays alert videos, and manages cameras.
4. **Mobile App (`flutter_app/`)**: A cross-platform app for volunteers/responders to receive alerts and view incidents.
