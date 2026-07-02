# THUYẾT MINH SẢN PHẨM SÁNG TẠO
*(Dự thi Tin học trẻ - Vòng khu vực)*

---

## ĐĂNG KÝ THÔNG TIN SẢN PHẨM DỰ THI
*[Placeholder: Điền thông tin theo mẫu của Ban tổ chức]*

## THÔNG TIN TÁC GIẢ (NHÓM TÁC GIẢ)
*[Placeholder: Điền thông tin cá nhân/nhóm của bạn]*

---
## GIỚI THIỆU VỀ SẢN PHẨM

### 1. Ý tưởng của sản phẩm
Từ thực trạng gia tăng áp lực giao thông và nguy cơ tai nạn tại nhiều nút giao, đặc biệt là các "điểm đen" vùng ven đô hoặc nông thôn nơi thiếu hạ tầng kết nối, em nhận thấy các giải pháp camera hiện tại chủ yếu chỉ mang tính "giám sát thụ động". Khi tai nạn xảy ra, việc cứu hộ thường chậm trễ do thiếu thông tin.

Từ đó, ý tưởng của dự án là xây dựng một **hệ sinh thái khép kín và chủ động**: "Hệ thống giám sát thông minh, cảnh báo sự cố và điều phối cứu hộ giao thông". Sản phẩm không chỉ dùng AI để **phát hiện** tức thì các sự cố (tai nạn, cháy nổ, kẹt xe), ghi lại đoạn video bằng chứng 10s, mà còn tự động tính toán khoảng cách để **điều phối Tình nguyện viên lân cận** thông qua ứng dụng trên điện thoại, nhằm tận dụng tối đa "thời gian vàng" cứu người bị nạn.

### 2. Giới thiệu tổng quan
Phương pháp tiếp cận của dự án là sự kết hợp đa nền tảng mạnh mẽ: AI/Computer Vision (xử lý hình ảnh) + Backend Cloud + Web Admin (quản lý trung tâm) + Mobile App (dành cho người dân tham gia cứu hộ). 

**Những phát hiện mới và giải pháp kỹ thuật xuất sắc trong quá trình triển khai:**
Quá trình làm dự án không hề dễ dàng, em đã tự nghiên cứu và vượt qua 3 rào cản kỹ thuật rất lớn, đây cũng là điểm sáng tạo cốt lõi của dự án:
- **Khắc phục giới hạn của hệ điều hành di động (Android Battery Saver):** Khi phát triển App cho tình nguyện viên, em phát hiện các máy Android (như Xiaomi, Oppo) thường tự động "giết" ứng dụng chạy ngầm, làm mất thông báo khẩn cấp. Em đã đào sâu tài liệu kiến trúc của Firebase Cloud Messaging (FCM) và chuyển đổi sang cấu trúc `"100% Data-Only Payload"`. Phương pháp này buộc hệ điều hành phải "đánh thức" luồng chạy ngầm (Isolate) của App để tự xây dựng thông báo khẩn, đảm bảo 100% tình nguyện viên nhận được tin báo dù máy đang khóa.
- **Khắc phục lỗi tràn bộ nhớ (Memory Leak) khi xử lý Video AI:** Khi hệ thống ghi hình liên tục 24/7, máy tính thường xuyên bị treo do cạn kiệt RAM (`_ArrayMemoryError`). Qua phân tích, em phát hiện nguyên nhân do bộ đệm đường ống (pipe buffer) của tiến trình FFmpeg bị đầy. Giải pháp định tuyến lại luồng `stdout` và `stderr` vào `DEVNULL` đã giúp hệ thống chạy mượt mà không giới hạn thời gian.
- **Thuật toán tính khoảng cách thông minh:** Nếu chỉ dùng công thức đường chim bay (Haversine) để tìm tình nguyện viên, hệ thống hay báo nhầm người ở gần nhưng bị ngăn cách bởi sông, hồ, đường cao tốc. Em đã tích hợp thuật toán định tuyến đường bộ nguồn mở OSRM, kết hợp cơ chế bộ nhớ đệm (Cache) 60 giây để tránh quá tải API, giúp việc điều phối cứu hộ cực kỳ chính xác.

---
## MÔ TẢ SẢN PHẨM

### 1. Chức năng chính của sản phẩm
**1.1. Mô tả rõ các tính năng của sản phẩm (Tính mới & Ưu điểm vượt trội)**
- **Nhận diện đa sự cố với Batch Inference:** Thay vì chỉ đếm xe, mô hình AI (YOLOv8/v11) phân tích thời gian thực các sự cố: Tai nạn, Cháy nổ, Tụ tập đông người. Cơ chế xử lý luồng (batch inference) giúp hệ thống dễ dàng mở rộng lên hàng chục camera.
- **Thuật toán "Bộ đệm video vòng lặp":** Camera luôn lưu tạm 5 giây video trong quá khứ. Khi có sự cố, hệ thống tự động nối thêm 5 giây hiện tại để tạo ra một đoạn video 10 giây hoàn chỉnh (trước và sau khi sự việc xảy ra), cung cấp bằng chứng pháp lý vô giá mà camera truyền thống ít làm được.
- **Hệ sinh thái điều phối cứu hộ đột phá (Web + Mobile App):**
  - **Trang Admin (Web):** Bản đồ số thời gian thực hiển thị vị trí camera và tình nguyện viên (GPS cập nhật liên tục 3s/lần). Cho phép Admin bấm nút gọi trực tiếp các lực lượng 113, 114, 115 và thông tin này lập tức đồng bộ lên màn hình của các tình nguyện viên.
  - **App Tình nguyện viên (Mobile):** Tự động sàng lọc bán kính, hiển thị bản đồ dẫn đường và danh sách các nhiệm vụ.
- **Tính năng giao tiếp (Chat đa phương tiện & Video Live WebRTC):** Tích hợp công nghệ WebRTC cho phép tình nguyện viên trên đường đi có thể xem trực tiếp camera hiện trường với độ trễ siêu thấp. Tích hợp phòng Chat nội bộ (âm thanh, hình ảnh) giữa Admin và Tình nguyện viên, tự động khóa (Read-only) khi sự cố kết thúc để bảo vệ tính toàn vẹn của bằng chứng.
- **Phần cứng năng lượng xanh:** Trạm giám sát thiết kế tự hành, sử dụng năng lượng mặt trời, hoạt động liên tục 24/7 (lưu trữ điện lên tới 7 ngày) mà không cần kéo điện lưới.

*[Placeholder: Chèn Hình ảnh Sơ đồ kiến trúc phần mềm tổng thể (Gồm AI -> Backend -> Web + Mobile)]*

**1.2. Mô tả nền tảng phát triển của sản phẩm**
**a. Đối với sản phẩm phần mềm**
- **Ngôn ngữ & Nền tảng:** 
  - Module AI & Xử lý hình ảnh: Ngôn ngữ `Python`, thư viện `OpenCV`, `PyTorch` (YOLO), `aiortc` (WebRTC).
  - Module Backend: Ngôn ngữ `Python` framework `FastAPI`, Cơ sở dữ liệu NoSQL `MongoDB`, `Firebase Admin SDK`.
  - Frontend Web Admin: `ReactJS`, `Vite`, `Ant Design`.
  - Mobile App Tình nguyện viên: Nền tảng `Flutter` (ngôn ngữ `Dart`), hoạt động mượt mà trên cả Android và iOS.
- **Mô tả hoạt động của phần mềm:**
  - AI liên tục phân tích luồng video (RTSP) từ camera. Khi phát hiện bất thường, nó xuất video và gửi (POST) lên Backend.
  - Backend lưu dữ liệu vào MongoDB, lập tức gửi (broadcast) qua WebSocket để trang Web báo động, đồng thời dùng API OSRM tính toán bán kính, bắn Push Notification cho các điện thoại lân cận.
  - Tình nguyện viên mở app nhận nhiệm vụ, GPS của họ liên tục gửi về Backend để Admin quan sát và điều phối, đồng thời trò chuyện qua hệ thống Chat nội bộ.

**b. Đối với sản phẩm phần cứng**
- **Vấn đề giải quyết:** Triển khai giám sát ở các khu vực thiếu điện lưới, thiếu ánh sáng vào ban đêm.
- **Thành phần cấu kiện:** Tấm pin năng lượng mặt trời, Bộ pin lưu trữ Lithium, Đèn chiếu sáng thông minh (tự bật sáng ban đêm), và Camera IP thu nhận hình ảnh.
- **Giao tiếp phần mềm & phần cứng:** Camera truyền luồng video (RTSP) qua mạng không dây (Wi-Fi/4G) về hệ thống phần mềm trung tâm. 

*[Placeholder: Chèn Hình ảnh mô hình phần cứng (Hình trụ đèn, tấm pin, camera như đã thiết kế)]*

**1.3. Kết luận**
- **Vấn đề đã giải quyết:** Sản phẩm không chỉ phát hiện sự cố tự động mà còn tạo ra một "mạng lưới nhân ái", kết nối và điều phối người dân tham gia cứu hộ trong "thời gian vàng". Đồng thời, hệ thống cung cấp video bằng chứng nguyên vẹn trước-sau sự cố cho cơ quan chức năng.
- **Ưu điểm:** Khả năng hoạt động khép kín, đa nền tảng. Khắc phục được các điểm yếu chí mạng về công nghệ hiện tại (thông báo ngầm trên điện thoại, tràn bộ nhớ hệ thống, độ trễ video). Chi phí vận hành thấp nhờ phần cứng độc lập.
- **Nhược điểm:** Phụ thuộc vào chất lượng kết nối mạng 4G/Wi-Fi tại điểm lắp đặt camera để truyền video về máy chủ. 

---
### 2. Đánh giá sản phẩm
**2.1. Tiềm năng ứng dụng**
Quy mô và phạm vi ứng dụng rất rộng lớn: từ các nút giao đô thị lớn đến các "điểm đen" giao thông ở vùng ngoại ô, đường quốc lộ xa dân cư. Đặc biệt, nhờ kiến trúc chuẩn (REST API, WebSocket), dự án cực kỳ dễ tích hợp và kết nối liên thông vào Trung tâm điều hành Thành phố thông minh (Smart City - IOC) của các địa phương, cho phép chia sẻ dữ liệu trực tiếp với Công an (113), Cứu hỏa (114), Y tế (115).

**2.2. Hiệu quả đem lại khi ứng dụng sản phẩm**
- **Về mặt kinh tế:** So với các hệ thống camera chuyên dụng đắt đỏ của nước ngoài, giải pháp của dự án tận dụng camera thường kết hợp AI phần mềm và năng lượng mặt trời, giúp giảm đến 70% chi phí hạ tầng. Giảm bớt nhân lực trực màn hình nhờ AI tự động phát hiện.
- **Về mặt xã hội:** Mang ý nghĩa nhân văn sâu sắc. Huy động được sức mạnh của cộng đồng tham gia cứu hộ, giảm thiểu rủi ro tắc nghẽn, tránh những thương vong đáng tiếc do chậm trễ cấp cứu. 

---
### 3. Yêu cầu đối với cơ sở hạ tầng cần thiết để triển khai (dành cho BTC)
Để chuẩn bị cho quá trình trình bày và chấm thi, nhóm em cần:
- 1 Bàn để đặt Laptop đóng vai trò máy chủ trung tâm (đã cài đặt sẵn toàn bộ môi trường phần mềm) và đặt Mô hình phần cứng (Trụ đèn, camera).
- 1 Mạng Wi-Fi ổn định (hoặc BTC cho phép nhóm tự chuẩn bị bộ phát 4G/Router) để các thiết bị (Laptop, Điện thoại giám khảo, Điện thoại thí sinh) kết nối nội bộ với nhau.
- Nguồn điện 220V cho Laptop và các thiết bị trình diễn.

### 4. Thời gian phát triển sản phẩm
- **Số tháng:** 6 tháng (Từ tháng 12/2025 đến tháng 6/2026).

### 5. Hướng dẫn sử dụng
1. Khởi động file kịch bản `start.bat` trên máy chủ để bật đồng loạt toàn bộ dịch vụ (AI, Backend, Web).
2. Trọng tài/Ban giám khảo dùng trình duyệt web truy cập vào Dashboard Admin để quan sát toàn hệ thống.
3. Cài đặt file App Flutter (APK) trên điện thoại, đăng ký tài khoản Tình nguyện viên và chọn bán kính hoạt động.
4. Kích hoạt tình huống giả định (đưa video tai nạn/cháy qua camera, hoặc bấm nút "Test Alert" trên Web).
5. Trải nghiệm luồng hệ thống: Web báo động -> Điện thoại tình nguyện viên nhận Push Notification -> Chấp nhận nhiệm vụ -> Xem Live Video & Chat với Ban giám khảo trên Web Admin.

### 6. Tự đánh giá mặt tồn tại cần khắc phục
- AI đôi khi còn bị nhầm lẫn trong điều kiện thời tiết quá khắc nghiệt (mưa bão rất to) hoặc góc quay camera bị che khuất. Khắc phục bằng cách tiếp tục mở rộng tập dữ liệu huấn luyện (Dataset).
- Cần nghiên cứu đưa AI xuống xử lý trực tiếp tại Camera (Edge AI trên các board mạch như Jetson Nano) để giảm băng thông truyền tải video liên tục về máy chủ.

---
## KẾT LUẬN

### 1. Hướng phát triển của sản phẩm trong tương lai
- **Hệ thống điểm thưởng (Gamification):** Hoàn thiện hệ thống tích điểm, thăng hạng (Cấp bậc: Hiệp sĩ đường phố, Anh hùng cứu nạn,...) cho tình nguyện viên để lan tỏa phong trào và khuyến khích cộng đồng tham gia bền vững.
- **Phát hiện hành vi nguy hiểm khác:** Bổ sung AI nhận diện các hành vi như đi ngược chiều, không đội mũ bảo hiểm, chở quá số người quy định.
- **Phối hợp đa phương tiện:** Nâng cấp tính năng Chat cho phép Tình nguyện viên Livestream trực tiếp bằng camera điện thoại của họ gửi về trung tâm chỉ huy.

### 2. Nguyện vọng trong tương lai
Sản phẩm không chỉ là một dự án dự thi mà là tâm huyết của em hướng đến cộng đồng. Em nguyện vọng dự án sẽ nhận được sự cố vấn từ các chuyên gia, và được các cấp chính quyền, Sở ban ngành quan tâm để có thể thí điểm thực tế tại một số "điểm đen" giao thông. Khát vọng lớn nhất của em là ứng dụng công nghệ để cứu được tính mạng con người và lan tỏa tình người trong xã hội.

---
## TÀI LIỆU THAM KHẢO
1. R. Szeliski, *Computer Vision: Algorithms and Applications*, Springer, 2nd Edition, 2022.
2. J. Redmon, S. Divvala, *You Only Look Once: Unified, Real-Time Object Detection*, CVPR, 2016.
3. Tài liệu kiến trúc nền tảng Flutter (https://flutter.dev) và FastAPI (https://fastapi.tiangolo.com).
4. Báo cáo tình hình an toàn giao thông của Ủy ban ATGT Quốc gia (2025).

---
## CAM KẾT
Chúng tôi cam kết SPST dự thi chưa từng đạt giải tại các cuộc thi, hội thi cấp quốc gia hay quốc tế. Nếu sai phạm, chúng tôi xin chịu mọi hình thức xử lý theo quy định của Ban tổ chức.

Đà Nẵng, ngày 01 tháng 07 năm 2026
**Chữ ký của tác giả/nhóm tác giả**
*[Ký và ghi rõ họ tên]*
