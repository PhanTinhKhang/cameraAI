import { Modal, Row, Col, Card, List, Tag, Badge, Typography, Button, Input, Upload, message } from "antd";
import { useEffect, useState, useRef } from "react";
import WebRTCPlayer from "./WebRTCPlayer";
import MapView from "./MapView";
import { UserOutlined, MedicineBoxOutlined, ToolOutlined, SafetyOutlined, SendOutlined, PictureOutlined, AudioOutlined, AudioMutedOutlined } from "@ant-design/icons";

const { Text, Title } = Typography;

export default function FocusPanel({ alert, apiUrl, open, onCancel, onAction }) {
  const [trackingData, setTrackingData] = useState([]);
  const [chatText, setChatText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [showPlayback, setShowPlayback] = useState(false);
  const messagesEndRef = useRef(null);
  const timerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const streamRef = useRef(null);

  useEffect(() => {
    if (!open || !alert) {
      setTrackingData([]);
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      setIsRecording(false);
      return;
    }

    setShowPlayback(alert.status === "closed");

    const fetchTracking = async () => {
      try {
        const res = await fetch(`${apiUrl}/api/alerts/${alert._id || alert.id}/tracking`);
        if (res.ok) {
          const data = await res.json();
          if (data.tracking) {
            setTrackingData(prev => {
              if (prev.length > 0 && data.tracking.length > prev.length) {
                try {
                  const AudioContext = window.AudioContext || window.webkitAudioContext;
                  if (AudioContext) {
                    const ctx = new AudioContext();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.connect(gain); gain.connect(ctx.destination);
                    osc.type = 'triangle'; osc.frequency.setValueAtTime(400, ctx.currentTime);
                    osc.frequency.exponentialRampToValueAtTime(600, ctx.currentTime + 0.1);
                    gain.gain.setValueAtTime(0, ctx.currentTime);
                    gain.gain.linearRampToValueAtTime(0.3, ctx.currentTime + 0.05);
                    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
                    osc.start(); osc.stop(ctx.currentTime + 0.2);
                  }
                } catch (e) {}
              }
              return data.tracking;
            });
          }
        }
      } catch (err) {
        console.error("Tracking fetch error:", err);
      }
    };

    // Fetch immediately
    fetchTracking();

    // Poll every 3 seconds as requested
    timerRef.current = setInterval(fetchTracking, 3000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [open, alert, apiUrl]);

  const [prevChatLen, setPrevChatLen] = useState(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView();
    if (alert?.messages && alert.messages.length > prevChatLen) {
      if (prevChatLen !== 0) {
        try {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (AudioContext) {
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(0.5, ctx.currentTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
          }
        } catch (e) {}
      }
      setPrevChatLen(alert.messages.length);
    }
  }, [alert?.messages]);

  const postMediaMessage = async (url, type) => {
    try {
      await fetch(`${apiUrl}/api/alerts/${alert._id || alert.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: "",
          type: type,
          content: url,
          sender: "admin",
          sender_id: "admin",
          name: "Trạm Điều Hành"
        })
      });
    } catch (err) {
      console.error("Chat media send error:", err);
    }
  };

  const handleMediaUpload = async (options) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${apiUrl}/api/alerts/${alert._id || alert.id}/chat/media`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      await postMediaMessage(data.url, "image");
      onSuccess("Ok");
    } catch (err) {
      onError(err);
      message.error("Lỗi tải lên hình ảnh");
    }
  };

  const startRecording = async () => {
    try {
      if (!streamRef.current) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      
      mediaRecorderRef.current = new MediaRecorder(streamRef.current);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        if (audioChunksRef.current.length === 0) return;
        
        const mimeType = mediaRecorderRef.current.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        if (audioBlob.size === 0) return;
        
        const formData = new FormData();
        const ext = mimeType.includes("mp4") ? "mp4" : "webm";
        formData.append("file", audioBlob, `audio.${ext}`);
        
        try {
          const res = await fetch(`${apiUrl}/api/alerts/${alert._id || alert.id}/chat/media`, {
            method: "POST",
            body: formData,
          });
          const data = await res.json();
          await postMediaMessage(data.url, "audio");
        } catch (err) {
          message.error("Lỗi tải lên âm thanh");
        }
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Mic error:", err);
      message.error("Không thể truy cập Microphone");
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const handleSendMessage = async () => {
    if (!chatText.trim() || alert.status === "closed") return;
    try {
      await fetch(`${apiUrl}/api/alerts/${alert._id || alert.id}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: "",
          type: "text",
          content: chatText.trim(),
          sender: "admin",
          sender_id: "admin",
          name: "Trạm Điều Hành"
        })
      });
      setChatText("");
    } catch (err) {
      console.error("Chat send error:", err);
    }
  };

  if (!alert) return null;

  // Render icons for specific roles/skills
  const renderIcon = (role) => {
    if (role === "y_te") return <MedicineBoxOutlined />;
    if (role === "cuu_ho") return <ToolOutlined />;
    if (role === "canh_sat") return <SafetyOutlined />;
    return <UserOutlined />;
  };

  const cameraData = [{
    id: alert._id || alert.id,
    name: alert.location,
    lat: alert.lat,
    lng: alert.lng,
    stream: alert.stream
  }];

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', paddingRight: 32 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Badge status={alert.status === "closed" ? "default" : "processing"} text={<strong style={{ fontSize: 16 }}>{alert.status === "closed" ? "Chế độ xem lại" : "Chế độ theo dõi"}</strong>} />
            <Tag color="red">{alert.type ? alert.type.toUpperCase() : "ALERT"}</Tag>
            <Text type="secondary">{alert.time || "N/A"}</Text>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>

            {alert.forces_called && alert.forces_called.includes("113") ? (
              <Button disabled size="small" style={{ color: '#52c41a', borderColor: '#52c41a' }}>🚓 Đã báo 113</Button>
            ) : (
              <Button type="primary" danger size="small" disabled={alert.status === "closed"} onClick={() => onAction && onAction(`/api/alerts/${alert.id || alert._id}/call_force`, { force: "113" })}>
                🚓 Báo 113
              </Button>
            )}
            {alert.forces_called && alert.forces_called.includes("114") ? (
              <Button disabled size="small" style={{ color: '#52c41a', borderColor: '#52c41a' }}>🚒 Đã báo 114</Button>
            ) : (
              <Button type="primary" danger size="small" disabled={alert.status === "closed"} onClick={() => onAction && onAction(`/api/alerts/${alert.id || alert._id}/call_force`, { force: "114" })}>
                🚒 Báo 114
              </Button>
            )}
            {alert.forces_called && alert.forces_called.includes("115") ? (
              <Button disabled size="small" style={{ color: '#52c41a', borderColor: '#52c41a' }}>🚑 Đã báo 115</Button>
            ) : (
              <Button type="primary" danger size="small" disabled={alert.status === "closed"} onClick={() => onAction && onAction(`/api/alerts/${alert.id || alert._id}/call_force`, { force: "115" })}>
                🚑 Báo 115
              </Button>
            )}
            {alert.status !== "closed" && (
              <Button size="small" type="dashed" onClick={() => setShowPlayback(!showPlayback)}>
                {showPlayback ? "🔴 Xem trực tiếp" : "📼 Xem phát lại"}
              </Button>
            )}
            {alert.status !== "closed" && (
              <Button
                size="small"
                onClick={() => {
                  if (onAction) onAction(`/api/alerts/${alert.id || alert._id}/close`);
                  if (onCancel) onCancel();
                }}
              >
                ✅ Đóng cảnh báo
              </Button>
            )}
          </div>
        </div>
      }
      open={open}
      onCancel={onCancel}
      footer={null}
      width={1400}
      bodyStyle={{ padding: 12, height: '80vh', overflow: 'hidden' }}
      destroyOnClose
    >
      <Row gutter={16} style={{ height: "100%" }}>
        {/* LEFT: Live Camera or Playback */}
        <Col span={11} style={{ height: "100%", display: "flex", flexDirection: "column" }}>
          <Card 
            title={showPlayback ? "📼 Video xem lại" : "🔴 Live Camera"} 
            size="small" 
            style={{ height: "100%", display: "flex", flexDirection: "column" }}
            bodyStyle={{ flex: 1, padding: 0, position: "relative", background: "#000" }}
          >
            {showPlayback ? (
              <video
                src={alert.video_url || (alert.video ? `${apiUrl}/videos/${alert.video.split("/").pop()}` : '')}
                controls
                autoPlay
                style={{ width: "100%", height: "100%", borderRadius: 8, background: "#000", objectFit: "contain" }}
              />
            ) : (
              <WebRTCPlayer url={`${apiUrl}/offer/${alert.camera_id || "cam01"}`} />
            )}
          </Card>
        </Col>

        {/* MIDDLE: Map & Volunteers */}
        <Col span={7} style={{ height: "100%", display: "flex", flexDirection: "column", gap: 16 }}>
          <Card
            title="📍 Bản Đồ & Vị Trí"
            size="small"
            style={{ height: "50%", display: "flex", flexDirection: "column" }}
            bodyStyle={{ flex: 1, padding: 0, position: "relative" }}
          >
            {alert.lat && alert.lng ? (
              <MapView
                cameras={cameraData}
                volunteers={trackingData}
                small={false}
                disablePopup={true}
              />
            ) : (
              <div style={{ padding: 20, textAlign: 'center' }}>Chưa có tọa độ GPS</div>
            )}
          </Card>

          <Card
            title={`👥 Lực lượng đã điều phối (${(alert.status === "closed" && alert.volunteers ? alert.volunteers : trackingData).length})`}
            size="small"
            style={{ height: "50%", overflowY: "auto" }}
          >
            <List
              dataSource={alert.status === "closed" && alert.volunteers ? alert.volunteers : trackingData}
              renderItem={(vol) => {
                const statusText = vol.status === 'completed' ? 'Hoàn thành' : vol.status === 'false_alarm' ? 'Báo giả' : 'Tham gia cứu hộ';
                const statusColor = vol.status === 'completed' ? 'green' : vol.status === 'false_alarm' ? 'red' : 'orange';
                return (
                  <List.Item>
                    <List.Item.Meta
                      avatar={<Badge dot color="green">{renderIcon(vol.role)}</Badge>}
                      title={vol.name}
                      description={
                        <div>
                          <div>Vai trò: <Tag color="blue">{vol.role}</Tag></div>
                          {vol.skills && <div>Kỹ năng: {vol.skills}</div>}
                          {vol.phone && <div>SĐT: <strong>{vol.phone}</strong></div>}
                          <div>Trạng thái: <Tag color={statusColor}>{statusText}</Tag></div>
                          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                            GPS: {Number(vol.lat)?.toFixed(5) || 'N/A'}, {Number(vol.lng)?.toFixed(5) || 'N/A'}
                          </div>
                        </div>
                      }
                    />
                  </List.Item>
                );
              }}
            />
            {trackingData.length === 0 && (
              <div style={{ textAlign: "center", color: "#888", marginTop: 20 }}>
                Đang chờ tình nguyện viên tiếp nhận...
              </div>
            )}
          </Card>
        </Col>

        {/* RIGHT: Chat Box */}
        <Col span={6} style={{ height: "100%", display: "flex", flexDirection: "column" }}>
          <Card 
            title="💬 Kênh Trò Chuyện" 
            size="small" 
            style={{ height: "100%", display: "flex", flexDirection: "column" }}
            bodyStyle={{ flex: 1, display: "flex", flexDirection: "column", padding: 8, overflow: "hidden" }}
          >
            <div style={{ flex: 1, overflowY: "auto", paddingRight: 8, display: "flex", flexDirection: "column", gap: 8 }}>
              {(alert.messages || []).length === 0 ? (
                <div style={{ textAlign: "center", color: "#888", marginTop: 20 }}>Chưa có tin nhắn nào</div>
              ) : (
                (alert.messages || []).map((msg, i) => {
                  const isAdmin = msg.sender === "admin";
                  return (
                    <div key={i} style={{ display: "flex", justifyContent: isAdmin ? "flex-end" : "flex-start" }}>
                      <div style={{ 
                        maxWidth: "90%", 
                        padding: "6px 10px", 
                        borderRadius: 10, 
                        background: isAdmin ? "#1890ff" : "#f0f2f5",
                        color: isAdmin ? "#fff" : "#000",
                        fontSize: 13
                      }}>
                        <div style={{ fontSize: 11, opacity: 0.8, marginBottom: 2, display: "flex", justifyContent: "space-between", gap: 8 }}>
                          <strong>{msg.name}</strong>
                          <span>{msg.timestamp?.split(' ')[1]}</span>
                        </div>
                        <div style={{ marginTop: 2 }}>
                          {msg.type === 'image' && (
                            <img src={msg.content.startsWith('/') ? apiUrl + msg.content : msg.content} alt="Media" style={{ maxWidth: '100%', borderRadius: 8 }} />
                          )}
                          {msg.type === 'audio' && (
                            <audio controls src={msg.content.startsWith('/') ? apiUrl + msg.content : msg.content} style={{ height: 30, maxWidth: 200 }} />
                          )}
                          {msg.type === 'text' && (
                            <div style={{ wordBreak: 'break-word' }}>{msg.content}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>
            
            {alert.status === "closed" ? (
              <div style={{ marginTop: 8, textAlign: 'center', color: 'red', fontStyle: 'italic' }}>
                Kênh trò chuyện đã đóng vì cảnh báo đã kết thúc.
              </div>
            ) : (
              <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                <Upload
                  showUploadList={false}
                  customRequest={handleMediaUpload}
                  accept="image/*"
                >
                  <Button icon={<PictureOutlined />} />
                </Upload>
                <Button 
                  icon={isRecording ? <AudioOutlined /> : <AudioMutedOutlined />} 
                  onClick={toggleRecording}
                  type={isRecording ? "primary" : "default"}
                  danger={isRecording}
                />
                <Input 
                  placeholder="Nhập tin nhắn..." 
                  value={chatText}
                  onChange={e => setChatText(e.target.value)}
                  onPressEnter={handleSendMessage}
                />
                <Button type="primary" icon={<SendOutlined />} onClick={handleSendMessage}>Gửi</Button>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </Modal>
  );
}
