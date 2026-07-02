import { Modal } from "antd";

export default function VideoPlayerModal({ open, onClose, video }) {
  if (!video) return null;

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={900}
      title="📼 Alert Playback"
      destroyOnClose
    >
      <video
        src={video}
        controls
        autoPlay
        style={{
          width: "100%",
          borderRadius: 12,
          background: "#000"
        }}
      />
    </Modal>
  );
}
