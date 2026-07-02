import { useEffect, useRef, useState } from "react";

export default function WebRTCPlayer({ url }) {
  const videoRef = useRef(null);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const reconnectTimeout = useRef(null);
  const retryCount = useRef(0);

  useEffect(() => {
    if (!url) return;
    
    let pc = null;
    let isActive = true;

    async function start() {
      if (!isActive) return;

      try {
        pc = new RTCPeerConnection({
          iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
        });

        pc.ontrack = (event) => {
          console.log("🎥 TRACK RECEIVED");
          if (videoRef.current) {
            videoRef.current.srcObject = event.streams[0];
          }
          setIsReconnecting(false);
          retryCount.current = 0; // Reset retry count on success
        };

        pc.oniceconnectionstatechange = () => {
          console.log("WebRTC ICE State:", pc.iceConnectionState);
          if (pc.iceConnectionState === "disconnected" || pc.iceConnectionState === "failed") {
            handleReconnect();
          }
        };

        pc.addTransceiver("video", { direction: "recvonly" });

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sdp: offer.sdp,
            type: offer.type,
          }),
        });

        if (!res.ok) {
          throw new Error(`Failed to fetch: ${res.status}`);
        }

        const answer = await res.json();
        await pc.setRemoteDescription(answer);

      } catch (err) {
        console.error("WebRTC Error:", err);
        handleReconnect();
      }
    }

    function handleReconnect() {
      if (!isActive) return;
      setIsReconnecting(true);
      if (pc) {
        pc.close();
        pc = null;
      }
      
      const backoff = Math.min(1000 * Math.pow(2, retryCount.current), 30000); // Max 30s
      retryCount.current += 1;
      console.log(`Reconnecting WebRTC in ${backoff}ms...`);
      
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = setTimeout(() => {
        start();
      }, backoff);
    }

    start();

    return () => {
      isActive = false;
      clearTimeout(reconnectTimeout.current);
      if (pc) pc.close();
    };
  }, [url]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", background: "#000" }}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ width: "100%", height: "100%", objectFit: "contain" }}
      />
      {isReconnecting && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.5)",
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          color: "white", zIndex: 10
        }}>
          <div style={{
            width: "30px", height: "30px",
            border: "3px solid rgba(255,255,255,0.3)",
            borderRadius: "50%",
            borderTopColor: "white",
            animation: "spin 1s ease-in-out infinite",
            marginBottom: "10px"
          }} />
          <style>
            {`
              @keyframes spin {
                to { transform: rotate(360deg); }
              }
            `}
          </style>
          Reconnecting...
        </div>
      )}
    </div>
  );
}
