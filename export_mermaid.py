import zlib
import base64
import urllib.request
import os

def generate_kroki_url(diagram_type, text):
    compressed = zlib.compress(text.encode('utf-8'))
    b64 = base64.urlsafe_b64encode(compressed).decode('utf-8')
    return f"https://kroki.io/{diagram_type}/png/{b64}"

arch_mmd = """graph TD
    subgraph arch1 ["Phần cứng (Trạm Camera)"]
        Solar[Pin Năng lượng mặt trời]
        Cam[Camera IP hiện hữu / lắp mới]
        LED[Đèn chiếu sáng tự động]
        Solar --> Cam
        Solar --> LED
    end

    subgraph arch2 ["Khối Xử lý AI (Python)"]
        Cam -->|Luồng RTSP| YOLO[Mô hình YOLO phân tích song song]
        YOLO -->|Lưu Video 10s| FFmpeg[Trình xuất Video FFmpeg]
        YOLO -->|Hình ảnh trực tiếp| WebRTC[Máy chủ WebRTC]
    end

    subgraph arch3 ["Khối Máy chủ Trung tâm (FastAPI)"]
        FFmpeg -->|Đẩy Cảnh báo| API[REST API]
        API --> DB[(MongoDB)]
        API --> WS[Máy chủ WebSocket]
        API --> OSRM[Thuật toán định tuyến OSRM]
        OSRM --> Firebase[Dịch vụ Firebase Cloud Messaging]
    end

    subgraph arch4 ["Người dùng đầu cuối"]
        WS -->|Cập nhật cảnh báo| WebAdmin[Admin Dashboard]
        WebRTC -->|Xem trực tiếp| WebAdmin
        Firebase -->|Push Notification| App[Ứng dụng Di động Volunteer App]
        WebRTC -->|Xem trực tiếp| App
        App -->|Đồng bộ GPS liên tục| API
    end"""

flow_mmd = """graph TD
    Start([Khởi động hệ thống]) --> RTSP[Kết nối luồng Video RTSP từ Camera]
    RTSP --> Split{Phân nhánh luồng}
    
    Split --> Stream[Phát trực tiếp lên Admin Dashboard]
    Split --> Buffer[Ghi đệm vòng lặp 5 giây Video]
    Split --> AI[Mô hình AI phân tích]
    
    AI --> Check{Phát hiện tai nạn/cháy/kẹt xe?}
    
    Check -->|Không| Pop[Xóa khung hình cũ nhất, tiếp tục ghi đệm]
    Pop --> AI
    
    Check -->|Có| PostRec[Ghi thêm 5 giây hình ảnh sau sự cố]
    PostRec --> Save[Đóng gói thành Video 10 giây làm bằng chứng]
    
    Save --> Server[Gửi Cảnh báo + Video lên Backend]
    
    Server --> Web[Phát chuông báo động trên Bản đồ Web]
    Server --> Calc[Tính khoảng cách đường bộ đến Tình nguyện viên]
    
    Calc --> Range{TNV nằm trong bán kính cứu hộ?}
    
    Range -->|Không| Skip[Bỏ qua]
    Range -->|Có| FCM[Gửi Push Notification cầu viện]
    
    FCM --> Mobile[App Tình nguyện viên rung chuông]
    Mobile --> Accept{Bấm chấp nhận cứu hộ?}
    
    Accept -->|Có| LiveTrack[Mở bản đồ dẫn đường, bật định vị GPS & Live Chat]
    Accept -->|Không| End([Chờ sự cố khác])
    LiveTrack --> End"""

try:
    print("Fetching Architecture Diagram...")
    arch_req = urllib.request.Request(generate_kroki_url('mermaid', arch_mmd), headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(arch_req) as response, open('d:/cameraAI2/so_do_kien_truc.png', 'wb') as out_file:
        out_file.write(response.read())
        
    print("Fetching Flowchart Diagram...")
    flow_req = urllib.request.Request(generate_kroki_url('mermaid', flow_mmd), headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(flow_req) as response, open('d:/cameraAI2/luu_do_thuat_toan.png', 'wb') as out_file:
        out_file.write(response.read())
        
    print("SUCCESS: Images generated successfully at d:/cameraAI2/")
except Exception as e:
    print(f"ERROR: {e}")
