import { useEffect, useRef } from "react";
import Hls from "hls.js";

export default function VideoPlayer({ stream }) {
  if (!stream)
    return (
      <div
        style={{
          height: "100%",
          background: "#000",
          color: "#999",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        Chọn camera để xem
      </div>
    );

  return (
    <video
      src={stream}
      controls
      autoPlay
      muted
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
        background: "#000",
      }}
    />
  );
}

