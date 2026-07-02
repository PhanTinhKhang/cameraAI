import cv2
import torch
from ultralytics import YOLO
import subprocess

device = "cuda" if torch.cuda.is_available() else "cpu"
RTSP_URL = "rtsp://localhost:8554/cam1"
#model_accident = YOLO("accident.pt").to(device)
model_fire = YOLO("best.pt").to(device)
#model_person = YOLO("person.pt").to(device)

cap = cv2.VideoCapture("rtsp://admin:L299411E@192.168.1.12:554/cam/realmonitor?channel=1&subtype=1&unicast=true&proto=Onvif")

width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


# ======================
# FFmpeg RTSP PIPE
# ======================
ffmpeg_cmd = [
    "ffmpeg",
    "-re",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", f"{width}x{height}",
    "-r", "15",
    "-i", "-",
    "-an",
    "-c:v", "h264_nvenc",
    "-preset", "p1",
    "-tune", "ll",
    "-rc", "cbr",
    "-b:v", "2M",
    "-maxrate", "2M",
    "-bufsize", "2M",
    "-bf", "0",
    "-g", "15",
    "-pix_fmt", "yuv420p",
    "-f", "rtsp",
    RTSP_URL
]
ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)


while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    #results_acc = model_accident(frame,classes=[0], conf=0.9,verbose=False)
    results_fire = model_fire(frame,classes=[0], conf=0.8,verbose=False)
    #results_person = model_person(frame, classes=[0], conf=0.9,verbose=False)

    # for result in results_acc:
    #     for box in result.boxes:
    #         x1, y1, x2, y2 = map(int, box.xyxy[0])
    #         conf = box.conf[0].item()
    #         cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
    #         cv2.putText(frame, f"Accident {conf:.2f}", (x1,y1-10),
    #                     cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    for result in results_fire:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf[0].item()
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,255), 2)
            cv2.putText(frame, f"Fire {conf:.2f}", (x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

    # for result in results_person:
    #     for box in result.boxes:
    #         x1, y1, x2, y2 = map(int, box.xyxy[0])
    #         cv2.rectangle(frame, (x1,y1), (x2,y2), (255,0,0), 2)
    #         cv2.putText(frame, "Person", (x1,y1-10),
    #                     cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)

    # ===== PUSH TO RTSP =====
    try:
        ffmpeg_process.stdin.write(frame.tobytes())
    except BrokenPipeError:
        break

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
