import React, { useState } from 'react';
import { Modal, Form, Input, InputNumber, Button, List, Space, Popconfirm } from 'antd';
import { DeleteOutlined, PlusOutlined, EditOutlined } from '@ant-design/icons';

export default function CameraSettingsModal({ open, onCancel, cameras, onSave }) {
  const [form] = Form.useForm();
  const [isAdding, setIsAdding] = useState(false);
  const [editingCamId, setEditingCamId] = useState(null);

  const handleSaveSubmit = (values) => {
    if (editingCamId) {
      // Update existing
      onSave(cameras.map(c => c.id === editingCamId ? { ...c, ...values } : c));
      setEditingCamId(null);
    } else {
      // Add new
      const nextIdNum = cameras.length > 0 ? Math.max(...cameras.map(c => parseInt(c.id.replace('cam', '') || 0))) + 1 : 1;
      const newCam = {
        id: `cam${String(nextIdNum).padStart(2, '0')}`,
        ...values
      };
      onSave([...cameras, newCam]);
    }
    setIsAdding(false);
    form.resetFields();
  };

  const startEdit = (cam) => {
    setEditingCamId(cam.id);
    setIsAdding(true);
    form.setFieldsValue(cam);
  };

  const handleDelete = (id) => {
    onSave(cameras.filter(c => c.id !== id));
  };

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      title="⚙️ Quản Lý Camera"
      footer={null}
      destroyOnClose
    >
      <List
        dataSource={cameras}
        renderItem={cam => (
          <List.Item
            actions={[
              <Button type="text" icon={<EditOutlined />} size="small" onClick={() => startEdit(cam)} />,
              <Popconfirm title="Xoá camera này?" onConfirm={() => handleDelete(cam.id)}>
                <Button danger icon={<DeleteOutlined />} size="small" />
              </Popconfirm>
            ]}
          >
            <List.Item.Meta
              title={cam.name}
              description={`RTSP: ${cam.rtsp_url} | Toạ độ: ${cam.lat}, ${cam.lng}`}
            />
          </List.Item>
        )}
      />
      
      {!isAdding ? (
        <Button 
          type="dashed" 
          block 
          icon={<PlusOutlined />} 
          onClick={() => {
            setEditingCamId(null);
            form.resetFields();
            setIsAdding(true);
          }}
          style={{ marginTop: 16 }}
        >
          Thêm Camera Mới
        </Button>
      ) : (
        <Form form={form} layout="vertical" onFinish={handleSaveSubmit} style={{ marginTop: 16, background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>
            {editingCamId ? 'Sửa Camera' : 'Thêm Camera Mới'}
          </div>
          <Form.Item name="name" label="Tên Camera" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="rtsp_url" label="RTSP URL hoặc WebCam ID (ví dụ: 0)" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="lat" label="Vĩ độ (Latitude)" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="lng" label="Kinh độ (Longitude)" rules={[{ required: true }]}>
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit">{editingCamId ? 'Cập Nhật' : 'Lưu'}</Button>
            <Button onClick={() => { setIsAdding(false); setEditingCamId(null); form.resetFields(); }}>Huỷ</Button>
          </Space>
        </Form>
      )}
    </Modal>
  );
}
