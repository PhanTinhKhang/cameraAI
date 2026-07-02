import { useEffect, useRef, useState } from "react";

export default function useAlertSound(alerts) {
  const lastAlertId = useRef(null); // Track ID của alert mới nhất
  const audioRef = useRef(null);
  const [isUnlocked, setIsUnlocked] = useState(false);

  useEffect(() => {
    // Khởi tạo audio
    if (!audioRef.current) {
      audioRef.current = new Audio("/alert.mp3");
      audioRef.current.volume = 0.7;
      audioRef.current.load();
    }

    // Unlock audio khi user click/touch bất kỳ đâu
    const unlockAudio = () => {
      if (!isUnlocked && audioRef.current) {
        audioRef.current.play()
          .then(() => {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            setIsUnlocked(true);
            console.log("🔊 Audio unlocked - ready to play alerts!");
          })
          .catch(() => {
            // Ignore error, sẽ tự động unlock ở lần tương tác tiếp theo
          });
      }
    };

    // Lắng nghe mọi tương tác của user
    document.addEventListener("click", unlockAudio);
    document.addEventListener("touchstart", unlockAudio);
    document.addEventListener("keydown", unlockAudio);

    return () => {
      document.removeEventListener("click", unlockAudio);
      document.removeEventListener("touchstart", unlockAudio);
      document.removeEventListener("keydown", unlockAudio);
    };
  }, [isUnlocked]);

  useEffect(() => {
    // Nếu chưa có alerts, khởi tạo lastAlertId
    if (alerts.length === 0) {
      lastAlertId.current = null;
      return;
    }

    // Lấy alert mới nhất
    const latestAlert = alerts[0];
    const currentAlertId = latestAlert._id || latestAlert.id || latestAlert.time;

    console.log("🔔 Alert check:", {
      currentAlertId,
      lastAlertId: lastAlertId.current,
      isNew: currentAlertId !== lastAlertId.current && lastAlertId.current !== null,
      isUnlocked: isUnlocked
    });

    // Kiểm tra xem có phải alert MỚI không (ID khác với alert trước đó)
    if (currentAlertId !== lastAlertId.current && lastAlertId.current !== null) {
      console.log("🚨 NEW ALERT DETECTED!", latestAlert.type);
      
      if (audioRef.current && isUnlocked) {
        console.log("🔊 Playing alert sound...");
        audioRef.current.currentTime = 0;
        audioRef.current.play()
          .then(() => {
            console.log("✅ Sound played successfully!");
          })
          .catch((err) => {
            console.warn("⚠️ Play failed:", err.message);
          });
      } else if (!isUnlocked) {
        console.warn("⚠️ Audio chưa unlock. Click vào trang để kích hoạt âm thanh.");
      }
    }
    
    // Update lastAlertId
    lastAlertId.current = currentAlertId;
  }, [alerts, isUnlocked]);

  return isUnlocked;
}