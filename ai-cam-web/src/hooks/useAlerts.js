import { useEffect, useRef, useState, useCallback } from "react";
import { notification } from "antd";

export default function useAlerts(focusAlertId = null) {
  const [alerts, setAlerts] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const retryCountRef = useRef(0);
  const isActiveRef = useRef(true);
  const focusAlertIdRef = useRef(focusAlertId);

  useEffect(() => {
    focusAlertIdRef.current = focusAlertId;
  }, [focusAlertId]);

  const playNotificationSound = useCallback(() => {
    try {
      const audio = new Audio('/alert.mp3');
      audio.volume = 0.5;
      audio.play().catch(e => console.log("Audio play error", e));
    } catch(e) {}
  }, []);

  const notifyIfUnfocused = useCallback((alertId, title, desc) => {
    if (String(alertId) !== String(focusAlertIdRef.current)) {
      notification.info({ message: title, description: desc, placement: "topRight" });
      playNotificationSound();
    }
  }, [playNotificationSound]);

  const fetchHistory = useCallback(async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/alerts?limit=0`, {
        headers: { "ngrok-skip-browser-warning": "true" }
      });
      if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
      const data = await res.json();
      setAlerts(data);
      console.log("📚 ALERT HISTORY LOADED", data.length);
    } catch (err) {
      console.error("❌ LOAD HISTORY FAILED", err);
    }
  }, []);

  const connectWs = useCallback(() => {
    if (!isActiveRef.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;

    console.log("Connecting WebSocket...");
    const wsUrl = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/alerts";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("✅ WS OPEN");
      retryCountRef.current = 0;
      fetchHistory();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log("📩 WS MSG RECEIVED", msg);

        // Fire side effects (notifications) OUTSIDE setAlerts to avoid duplicates
        if (msg.action === "chat_message") {
          notifyIfUnfocused(msg.alert_id, "Tin nhắn mới", msg.text || "Bạn có tin nhắn mới từ tình nguyện viên!");
        } else if (msg.action === "volunteer_added") {
          notifyIfUnfocused(msg.alert_id, "Tình nguyện viên mới", "Một tình nguyện viên vừa nhận tham gia cứu hộ!");
        } else if (msg.action === "volunteer_status_changed") {
          notifyIfUnfocused(msg.alert_id, "Cập nhật tình nguyện viên", "Tình nguyện viên vừa thay đổi trạng thái!");
        }

        // Pure state update — no side effects here
        setAlerts(prev => {
          const checkMatch = (a, mId) => {
            if (!mId) return false;
            return a._id === mId || a.id === mId;
          };

          if (msg.action === "update") {
            return prev.map(a => {
              const isMatch = checkMatch(a, msg._id) || checkMatch(a, msg.id) || checkMatch(a, msg.alert_id);
              return isMatch ? { ...a, ...msg } : a;
            });
          } else if (msg.action === "chat_message") {
            return prev.map(a => {
              if (checkMatch(a, msg.alert_id)) {
                return {
                  ...a,
                  messages: [...(a.messages || []), msg.message || msg]
                };
              }
              return a;
            });
          } else if (msg.action === "volunteer_added") {
            return prev.map(a => {
              if (checkMatch(a, msg.alert_id)) {
                const existing = (a.volunteers || []).find(v => v.user_id === msg.volunteer.user_id);
                if (existing) return a;
                return {
                  ...a,
                  volunteers: [...(a.volunteers || []), msg.volunteer]
                };
              }
              return a;
            });
          } else if (msg.action === "volunteer_status_changed") {
            return prev.map(a => {
              if (checkMatch(a, msg.alert_id)) {
                const updatedVolunteers = (a.volunteers || []).map(v => {
                  if (v.user_id === msg.user_id) {
                    return { ...v, status: msg.status };
                  }
                  return v;
                });
                return { ...a, volunteers: updatedVolunteers };
              }
              return a;
            });
          } else if (msg.action === "alert_closed") {
            return prev.map(a => {
              return checkMatch(a, msg.alert_id) ? { ...a, status: "closed" } : a;
            });
          } else {
            // New alert — only add if it has an _id or id field (is a real alert object)
            if (!msg._id && !msg.id) {
              console.log("⏭️ Skipping non-alert WS message:", msg);
              return prev;
            }
            const exists = prev.find(a => checkMatch(a, msg._id) || checkMatch(a, msg.id));
            if (exists) {
              return prev.map(a => (checkMatch(a, msg._id) || checkMatch(a, msg.id)) ? { ...a, ...msg } : a);
            }
            return [msg, ...prev];
          }
        });
      } catch (parseErr) {
        console.error("❌ Failed to parse WS message:", parseErr);
      }
    };

    ws.onerror = (e) => {
      console.error("❌ WS ERROR", e);
    };

    ws.onclose = (e) => {
      console.warn("⚠️ WS CLOSED", e.code, e.reason);
      // Prevent stale WebSockets (e.g. from React Strict Mode unmounts) from triggering reconnects
      if (ws !== wsRef.current) return;
      
      wsRef.current = null;
      if (isActiveRef.current) {
        const backoff = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
        retryCountRef.current += 1;
        console.log(`Reconnecting WS in ${backoff}ms...`);
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connectWs, backoff);
      }
    };
  }, [fetchHistory, notifyIfUnfocused]);

  useEffect(() => {
    isActiveRef.current = true;
    fetchHistory();
    connectWs();

    return () => {
      isActiveRef.current = false;
      clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWs, fetchHistory]);

  return alerts;
}
