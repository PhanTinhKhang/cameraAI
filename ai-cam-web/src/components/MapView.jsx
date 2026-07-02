import { GoogleMap, Marker, InfoWindow, useJsApiLoader } from "@react-google-maps/api";
import { Button } from "antd";
import { useState } from "react";

// cameras are now passed as props
const containerStyle = {
  width: "100%",
  height: "100%",
};

export default function MapView({ onSelect, small = false, cameras = [], volunteers = [], alerts = [], disablePopup = false }) {
  const [activeCam, setActiveCam] = useState(null);
  const [mapCenter, setMapCenter] = useState(null);

  const { isLoaded } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_KEY,
  });

  if (!isLoaded) return <div>Loading Map...</div>;

  if (cameras.length === 0) return <div>Đang tải bản đồ...</div>;

  // 🎯 CENTER = CAMERA
  const center = mapCenter || {
    lat: Number(cameras[0].lat),
    lng: Number(cameras[0].lng),
  };

  return (
    <GoogleMap
      mapContainerStyle={containerStyle}
      center={center}
      zoom={small ? 14 : 16}   // 🔥 zoom sát marker
      options={{
        disableDefaultUI: small,
        draggable: !small,
        scrollwheel: !small,
      }}
    >
      {/* CAMERA MARKERS */}
      {cameras.map((cam) => {
        const hasActiveAlert = alerts.some(a => a.camera_id === cam.id && a.status !== 'closed');
        return (
          <Marker
            key={cam.id}
            position={{ lat: Number(cam.lat), lng: Number(cam.lng) }}
            icon={hasActiveAlert ? undefined : { 
              url: "http://maps.google.com/mapfiles/ms/icons/blue-dot.png",
              scaledSize: new window.google.maps.Size(40, 40)
            }}
            onClick={() => {
              if (!disablePopup) {
                setActiveCam(cam);
                setMapCenter({ lat: Number(cam.lat), lng: Number(cam.lng) });
              }
            }}
          />
        );
      })}

      {/* VOLUNTEER MARKERS */}
      {volunteers.map((vol) => (
        <Marker
          key={vol.user_id}
          position={{ lat: Number(vol.lat), lng: Number(vol.lng) }}
          icon={{
            url: "http://maps.google.com/mapfiles/ms/icons/green-dot.png"
          }}
          title={`${vol.name} - ${vol.role}`}
        />
      ))}

      {activeCam && (
        <InfoWindow
          position={{ lat: activeCam.lat, lng: activeCam.lng }}
          onCloseClick={() => setActiveCam(null)}
        >
          <div
            style={{
              minWidth: 220,
              fontFamily: "Inter, system-ui",
            }}
          >
            {/* HEADER */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                marginBottom: 6,
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#ff4d4f",
                  display: "inline-block",
                  marginRight: 6,
                }}
              />
              LIVE · {activeCam.name}
            </div>

            {/* BUTTON */}
            <Button
              type="primary"
              block
              size="small"
              onClick={() => onSelect(`${import.meta.env.VITE_API_URL}/offer/${activeCam.id}`)}
              style={{
                borderRadius: 6,
                fontWeight: 500,
                marginBottom: 8,
              }}
            >
              👁  Xem Live Feed
            </Button>
            
            {/* MANUAL TRIGGERS */}
            <div style={{ display: 'flex', gap: 4 }}>
              <Button 
                size="small" 
                danger 
                style={{ flex: 1, fontSize: 11 }}
                onClick={() => {
                  if (window.confirm("Tạo cảnh báo GIẢ LẬP: CHÁY?")) {
                    fetch(`${import.meta.env.VITE_API_URL}/trigger/${activeCam.id}/fire`, { method: "POST" });
                  }
                }}
              >
                🔥 Cháy
              </Button>
              <Button 
                size="small" 
                style={{ flex: 1, fontSize: 11, borderColor: '#faad14', color: '#faad14' }}
                onClick={() => {
                  if (window.confirm("Tạo cảnh báo GIẢ LẬP: TAI NẠN?")) {
                    fetch(`${import.meta.env.VITE_API_URL}/trigger/${activeCam.id}/accident`, { method: "POST" });
                  }
                }}
              >
                💥 Tai nạn
              </Button>
              <Button 
                size="small" 
                style={{ flex: 1, fontSize: 11, borderColor: '#1890ff', color: '#1890ff' }}
                onClick={() => {
                  if (window.confirm("Tạo cảnh báo GIẢ LẬP: KẸT XE?")) {
                    fetch(`${import.meta.env.VITE_API_URL}/trigger/${activeCam.id}/congestion`, { method: "POST" });
                  }
                }}
              >
                🚗 Kẹt xe
              </Button>
            </div>
          </div>
        </InfoWindow>
      )}
    </GoogleMap>
  );
}
