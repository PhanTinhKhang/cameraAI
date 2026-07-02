import cv2
import asyncio
import torch
from ultralytics import YOLO

device = "cuda" if torch.cuda.is_available() else "cpu"

model_accident = YOLO("ver3.pt").to(device)
model_fire = YOLO("fire.pt").to(device)
model_person = YOLO("person.pt").to(device)

cap = cv2.VideoCapture("rtsp://admin:L299411E@10.221.211.214:554/cam/realmonitor?channel=1&subtype=0")
#cap = cv2.VideoCapture("D:/cameraAI2/ML/xemay1.mp4")

width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    results_acc = model_accident(frame,classes=[0], conf=0.7,verbose=False)
    results_fire = model_fire(frame, conf=0.7,verbose=False)
    results_person = model_person(frame, classes=[0, 2, 3, 5, 7], conf=0.4,verbose=False)

    for result in results_acc:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf[0].item()
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,0,255), 2)
            cv2.putText(frame, f"Accident {conf:.2f}", (x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)

    for result in results_fire:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = box.conf[0].item()
            cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,255), 2)
            cv2.putText(frame, f"Fire {conf:.2f}", (x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

    for result in results_person:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(frame, (x1,y1), (x2,y2), (255,0,0), 2)
            cv2.putText(frame, "Object", (x1,y1-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)



    display = cv2.resize(frame, (960, 540))
    cv2.imshow("Detection", display)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
