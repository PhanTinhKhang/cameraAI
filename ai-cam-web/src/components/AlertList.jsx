import { List, Tag } from "antd";
import { useState } from "react";
import VideoPlayerModal from "./VideoPlayerModal";

export default function AlertList({ alerts }) {
  const [videoUrl, setVideoUrl] = useState(null);

  return (
    <>
      <List
        dataSource={alerts}
        renderItem={(a) => (
          <List.Item
            style={{ cursor: "pointer" }}
            onClick={() =>
              setVideoUrl(
                `https://linoleum-devourer-kindred.ngrok-free.dev/videos/${a.video.split("/").pop()}`
              )
            }
          >
            <Tag color={
              a.type === "fire" ? "red" :
              a.type === "accident" ? "orange" : "blue"
            }>
              {a.type.toUpperCase()}
            </Tag>

            <div style={{ marginLeft: 10 }}>
              <b>{a.location}</b>
              <div style={{ fontSize: 12, opacity: 0.7 }}>{a.time}</div>
            </div>
          </List.Item>
        )}
      />

      <VideoPlayerModal
        open={!!videoUrl}
        video={videoUrl}
        onClose={() => setVideoUrl(null)}
      />
    </>
  );
}
