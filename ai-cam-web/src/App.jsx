import { useState, useEffect, useRef } from "react";
import { Layout, Menu, List, Typography, Tag, Card, Modal, Button, message, Space, Form, Input, InputNumber, DatePicker, Badge } from "antd";
import { VideoCameraOutlined, EnvironmentOutlined, SettingOutlined, WarningOutlined, BarChartOutlined } from "@ant-design/icons";
import dayjs from "dayjs";

import MapView from "./components/MapView";
import AlertStats from "./components/AlertStats";
import FocusPanel from "./components/FocusPanel";
import useAlerts from "./hooks/useAlerts";
import { formatTime } from "./utils/formatTime";
import WebRTCPlayer from "./components/WebRTCPlayer";
import useAlertSound from "./hooks/useAlertSound";
import CameraSettingsModal from "./components/CameraSettingsModal";

const { Header, Content, Sider } = Layout;
const { Title } = Typography;

export default function App() {
  const [stream, setStream] = useState(null);
  const [mainView, setMainView] = useState("map");
  const [focusAlert, setFocusAlert] = useState(null);
  const alerts = useAlerts(focusAlert?._id || focusAlert?.id);
  const audioUnlocked = useAlertSound(alerts);
  const [playbackVideo, setPlaybackVideo] = useState(null);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [viewedAlerts, setViewedAlerts] = useState(new Set());
  const [cameras, setCameras] = useState([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isStatsOpen, setIsStatsOpen] = useState(false);
  const [form] = Form.useForm();
  const initialLoadRef = useRef(true); // Track lần load đầu tiên
  const [filterDate, setFilterDate] = useState(dayjs());
  const [refreshKey, setRefreshKey] = useState(0);

  const [sidebarWidth, setSidebarWidth] = useState(400);
  const isDragging = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging.current) return;
      let newWidth = e.clientX;
      if (newWidth < 250) newWidth = 250;
      if (newWidth > 800) newWidth = 800;
      setSidebarWidth(newWidth);
    };
    const handleMouseUp = () => {
      isDragging.current = false;
      document.body.style.cursor = "default";
    };
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    fetch(`${apiUrl}/api/config/cameras`, {
      headers: { "ngrok-skip-browser-warning": "true" }
    })
      .then(res => res.json())
      .then(data => setCameras(data))
      .catch(err => console.error("Error loading cameras:", err));
  }, [apiUrl]);

  const handleSaveCameras = async (updatedCameras) => {
    try {
      const res = await fetch(`${apiUrl}/api/config/cameras`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "ngrok-skip-browser-warning": "true" 
        },
        body: JSON.stringify(updatedCameras),
      });
      if (res.ok) {
        setCameras(updatedCameras);
        setIsSettingsOpen(false);
        setRefreshKey(prev => prev + 1);
        message.success("Lưu cấu hình thành công!");
      }
    } catch (e) {
      message.error("Lỗi khi lưu cấu hình.");
    }
  };

  // Đánh dấu alerts từ DB (load lần đầu) là đã xem
  useEffect(() => {
    if (initialLoadRef.current && alerts.length > 0) {
      // Load lần đầu từ DB → đánh dấu tất cả là đã xem
      const initialAlertIds = alerts.map(alert => alert.id || alert.time);
      setViewedAlerts(new Set(initialAlertIds));
      initialLoadRef.current = false;
      console.log("📚 Initial alerts from DB marked as viewed:", initialAlertIds.length);
    }
  }, [alerts]);

  // Đồng bộ selectedAlert với danh sách alerts realtime
  useEffect(() => {
    if (selectedAlert) {
      const selectedId = selectedAlert._id || selectedAlert.id;
      const updatedAlert = alerts.find(a => (a._id || a.id) === selectedId);
      // Chỉ cập nhật nếu reference khác nhau (tức là có dữ liệu mới)
      if (updatedAlert && updatedAlert !== selectedAlert) {
        setSelectedAlert(updatedAlert);
      }
    }
    if (focusAlert) {
      const focusId = focusAlert._id || focusAlert.id;
      const updatedAlert = alerts.find(a => (a._id || a.id) === focusId);
      if (updatedAlert && updatedAlert !== focusAlert) {
        setFocusAlert(updatedAlert);
      }
    }
  }, [alerts, selectedAlert, focusAlert]);

  // Khi click xem video, đánh dấu alert đã xem
  const handleAlertClick = (alert) => {
    const alertId = alert.id || alert.time;
    
    // Đánh dấu đã xem
    setViewedAlerts(prev => new Set([...prev, alertId]));
    
    // Mở FocusPanel
    setFocusAlert(alert);
  };

  const handleAdminAction = async (actionUrl, data = null) => {
    try {
      const options = {
        method: "POST",
        headers: { "ngrok-skip-browser-warning": "true" }
      };
      if (data) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(data);
      }
      const res = await fetch(`${apiUrl}${actionUrl}`, options);
      if (res.ok) {
        message.success("Đã cập nhật trạng thái thành công!");
      } else {
        message.error("Lỗi khi cập nhật.");
      }
    } catch (e) {
      message.error("Lỗi kết nối.");
    }
  };

  const filteredAlerts = alerts.filter(a => {
    if (!filterDate) return true;
    return dayjs(a.time).isSame(filterDate, 'day');
  });

  return (
    <Layout style={{ height: "100vh" }}>
      {/* HEADER */}
      <Header style={{ 
        background: "#020617", 
        display: "flex", 
        alignItems: "center", 
        justifyContent: "space-between",
        padding: "0 24px"
      }}>
        <Title level={4} style={{ color: "#fff", margin: 0 }}>
          🔥 AI Camera Dashboard
        </Title>
        
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {/* Audio Status */}
          {!audioUnlocked && (
            <div style={{
              color: "#faad14",
              fontSize: 13,
              display: "flex",
              alignItems: "center",
              gap: 8
            }}>
              <span>🔇</span>
              <span>Click để bật âm thanh cảnh báo</span>
            </div>
          )}
          
          {/* Stats Button */}
          <Button 
            type="text" 
            icon={<BarChartOutlined style={{ color: "#fff", fontSize: 18 }} />} 
            onClick={() => setIsStatsOpen(true)}
          />
          
          {/* Settings Button */}
          <Button 
            type="text" 
            icon={<SettingOutlined style={{ color: "#fff", fontSize: 18 }} />} 
            onClick={() => {
              setIsSettingsOpen(true);
            }}
          />
        </div>
      </Header>

      <Layout style={{ height: "calc(100vh - 64px)", overflow: "hidden" }}>
        {/* SIDEBAR */}
        <Sider width={sidebarWidth} style={{ background: "#001529", padding: "10px", overflowY: "auto", position: "relative" }}>
          <div style={{ flex: 1, paddingRight: 4 }}>
              {/* CAMERA LIST */}
              <Card title="📷 Cameras" size="small" bordered={false} style={{ marginBottom: 8 }}>
                  <List
                    dataSource={cameras}
                    renderItem={(cam) => (
                      <List.Item
                        style={{ cursor: "pointer" }}
                        onClick={() => setStream(`${apiUrl}/offer/${cam.id}`)}
                      >
                        <VideoCameraOutlined style={{ marginRight: 8 }} />
                        {cam.name}
                      </List.Item>
                    )}
                  />
              </Card>

              {/* ALERTS LIST */}
              <Card
                title={
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span>🚨 Alerts ({filteredAlerts.length})</span>
                    <DatePicker 
                      size="small" 
                      value={filterDate}
                      onChange={(date) => setFilterDate(date)} 
                      placeholder="Chọn ngày" 
                      allowClear
                    />
                  </div>
                }
                size="small"
                bordered={false}
                style={{ marginBottom: 8 }}
                bodyStyle={{
                  padding: 0,
                  maxHeight: 300,
                  overflowY: "auto"
                }}
              >
                <List
                  dataSource={filteredAlerts}
                  renderItem={(alert) => {
                    const alertId = alert.id || alert.time;
                    const isNew = !viewedAlerts.has(alertId);
                    const isActive = alert.status !== "closed";
                    
                    return (
                      <List.Item
                        style={{
                          padding: "10px 12px",
                          cursor: "pointer",
                          borderRadius: 8,
                          background: isActive 
                            ? "linear-gradient(90deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.05))"
                            : "transparent",
                          border: isActive ? "1px solid rgba(239, 68, 68, 0.5)" : "none",
                          transform: isActive ? "scale(1.02)" : "scale(1)",
                          transition: "all 0.3s ease",
                          animation: isActive ? "pulse 1s ease-in-out infinite" : "none",
                        }}
                        onClick={() => handleAlertClick(alert)}
                      >
                        <div style={{ width: "100%" }}>
                          <div style={{ 
                            marginBottom: 6,
                            display: "flex",
                            alignItems: "center",
                            gap: 6
                          }}>
                            {alert.type === "fire" && <Tag color="red">🔥 CHÁY</Tag>}
                            {alert.type === "congestion" && <Tag color="blue">👥 KẸT XE</Tag>}
                            {alert.type === "accident" && <Tag color="orange">🚗 TAI NẠN</Tag>}
                            
                            {isNew && (
                              <Tag 
                                color="red" 
                                style={{ 
                                  fontSize: 10,
                                  padding: "0 6px",
                                  fontWeight: 600
                                }}
                              >
                                MỚI
                              </Tag>
                            )}
                          </div>

                          <div style={{ fontWeight: 600, fontSize: 14 }}>
                            📍 {alert.location}
                          </div>

                          <div style={{ fontSize: 12, color: "#9ca3af" }}>
                            🕒 {formatTime(alert.time)}
                          </div>
                          
                          <div style={{ fontSize: 12, color: "#1890ff", marginTop: 4 }}>
                            🤝 {alert.volunteers?.length || 0} Người tình nguyện
                            {alert.status === "closed" && <Tag color="default" style={{marginLeft: 8}}>Đã Đóng</Tag>}
                            {alert.forces_called && alert.forces_called.length > 0 ? (
                              <Tag color="green" style={{marginLeft: 8}}>Đã báo: {alert.forces_called.join(", ")}</Tag>
                            ) : alert.rescue_sent ? (
                              <Tag color="green" style={{marginLeft: 8}}>Đã Báo Cứu Hộ</Tag>
                            ) : null}
                            {alert.volunteers && alert.volunteers.length > 0 && (
                              <div style={{ color: "#666", fontSize: 11, marginTop: 4 }}>
                                {alert.volunteers.map(v => {
                                    const statusText = v.status === 'completed' ? 'Hoàn thành' : v.status === 'false_alarm' ? 'Báo giả' : 'Tham gia cứu hộ';
                                    const skillText = v.skills ? `(${v.skills})` : '';
                                    return `${v.name}${skillText}: ${statusText}`;
                                }).join(', ')}
                              </div>
                            )}
                          </div>
                        </div>
                      </List.Item>
                    );
                  }}
                />
              </Card>

              {/* PREVIEW CARD */}
              <Card
                title={mainView === "map" ? "🎥 Live Camera" : "🗺 Map Preview"}
                size="small"
                bordered={false}
                style={{ height: 300, cursor: "pointer", display: "flex", flexDirection: "column" }}
                bodyStyle={{ padding: 0, flex: 1, position: "relative" }}
                onClick={() => setMainView(mainView === "map" ? "cam" : "map")}
              >
                <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
                  {mainView === "map" ? (
                    stream ? (
                      <WebRTCPlayer key={stream + refreshKey} url={stream} />
                    ) : (
                      <div style={{ color: "#888", padding: 12 }}>
                        Chọn camera để xem
                      </div>
                    )
                  ) : (
                    <MapView
                      key="map-sider"
                      small
                      cameras={cameras}
                      alerts={alerts}
                      onSelect={setStream}
                    />
                  )}
                </div>
              </Card>
            </div>

            {/* DRAG HANDLE */}
            <div
              onMouseDown={() => {
                isDragging.current = true;
                document.body.style.cursor = "col-resize";
              }}
              style={{
                position: "absolute",
                right: 0,
                top: 0,
                bottom: 0,
                width: 6,
                cursor: "col-resize",
                background: "#303030",
                zIndex: 10
              }}
            />
        </Sider>

        {/* MAIN CONTENT */}
        <Content style={{ position: "relative", background: "#fff" }}>
          <div style={{ height: "100%", borderRadius: 8, overflow: "hidden", position: "relative" }}>
            {mainView === "map" ? (
              <MapView
                key="map-main"
                cameras={cameras}
                alerts={alerts}
                onSelect={setStream}
              />
            ) : (
              stream ? (
                <WebRTCPlayer key={stream + refreshKey} url={stream} />
              ) : (
                <div style={{ color: "#888", display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
                  Chưa chọn camera
                </div>
              )
            )}
          </div>
        </Content>
      </Layout>

      {/* SETTINGS MODAL */}
      <CameraSettingsModal 
        open={isSettingsOpen}
        onCancel={() => setIsSettingsOpen(false)}
        cameras={cameras}
        onSave={handleSaveCameras}
      />

      {/* CSS ANIMATION */}
      <style>{`
        @keyframes pulse {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
          }
          50% {
            box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
          }
        }
      `}</style>

      {/* ALERT STATS MODAL */}
      <AlertStats 
        open={isStatsOpen} 
        onCancel={() => setIsStatsOpen(false)} 
        alerts={alerts} 
        cameras={cameras}
      />

      {/* FOCUS PANEL MODAL */}
      <FocusPanel
        open={!!focusAlert}
        onCancel={() => setFocusAlert(null)}
        alert={focusAlert}
        apiUrl={apiUrl}
        onAction={handleAdminAction}
      />
    </Layout>
  );
}