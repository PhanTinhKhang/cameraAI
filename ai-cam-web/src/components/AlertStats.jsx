import { useState, useMemo } from 'react';
import { Modal, Row, Col, Card, Statistic, Select } from 'antd';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell } from 'recharts';
import dayjs from 'dayjs';

const COLORS = {
  accident: '#faad14', // Orange
  fire: '#f5222d',     // Red
  congestion: '#1890ff' // Blue
};

const LABELS = {
  accident: 'Tai Nạn',
  fire: 'Cháy',
  congestion: 'Kẹt Xe'
};

export default function AlertStats({ open, onCancel, alerts = [], cameras = [] }) {
  const [timeRange, setTimeRange] = useState('7'); // days
  const [selectedCamera, setSelectedCamera] = useState('all');

  // Process data for charts
  const stats = useMemo(() => {
    try {
      const now = dayjs();
      const filteredAlerts = alerts.filter(a => {
        const alertDate = dayjs(a.time);
        
        // Date filter
        let inDateRange = false;
        if (timeRange === '1') {
          inDateRange = alertDate.isSame(now, 'day');
        } else {
          inDateRange = alertDate.isAfter(now.subtract(parseInt(timeRange), 'day').startOf('day'));
        }

        // Camera filter
        let matchesCamera = true;
        if (selectedCamera !== 'all') {
          // Assuming alert.location matches camera.name or camera.stream or something similar
          // Will match alert.location to selectedCamera (camera name)
          matchesCamera = a.location === selectedCamera;
        }

        return inDateRange && matchesCamera;
      });

      // 1. By Type
      const typeCount = { accident: 0, fire: 0, congestion: 0 };
      filteredAlerts.forEach(a => {
        if (typeCount[a.type] !== undefined) typeCount[a.type]++;
      });
      
      const typeData = Object.keys(typeCount).map(key => ({
        name: LABELS[key] || key,
        value: typeCount[key],
        type: key
      }));

      // 2. By Day (for BarChart)
      const dayMap = {};
      for (let i = parseInt(timeRange) - 1; i >= 0; i--) {
        const dStr = now.subtract(i, 'day').format('MM-DD');
        dayMap[dStr] = { name: dStr, accident: 0, fire: 0, congestion: 0 };
      }
      
      filteredAlerts.forEach(a => {
        const dayStr = dayjs(a.time).format('MM-DD');
        if (dayMap[dayStr] && dayMap[dayStr][a.type] !== undefined) {
          dayMap[dayStr][a.type]++;
        }
      });

      const trendData = Object.values(dayMap);

      // 3. Response Time (Average time to close) -> CHANGED TO RESOLVED ALERTS
      let resolvedCount = 0;
      let totalVolunteers = 0;

      filteredAlerts.forEach(a => {
        totalVolunteers += (a.volunteers?.length || 0);
        if (a.status === 'closed') {
          resolvedCount++;
        }
      });

      return {
        total: filteredAlerts.length,
        resolvedCount,
        totalVolunteers,
        typeData,
        trendData
      };
    } catch (e) {
      console.error("Stats Error:", e);
      return { total: 0, resolvedCount: 0, totalVolunteers: 0, typeData: [], trendData: [] };
    }
  }, [alerts, timeRange, selectedCamera]);

  if (!stats) return <Modal open={open} onCancel={onCancel} title="Error"><div>Stats failed to load</div></Modal>;

  return (
    <Modal
      title="📊 Thống Kê Cảnh Báo"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={800}
      destroyOnClose
    >
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
        <Select 
          value={selectedCamera} 
          onChange={setSelectedCamera} 
          style={{ width: 200 }}
          options={[
            { value: 'all', label: 'Tất cả Camera' },
            ...cameras.map(cam => ({ value: cam.name, label: cam.name }))
          ]}
        />
        <Select 
          value={timeRange} 
          onChange={setTimeRange} 
          style={{ width: 150 }}
          options={[
            { value: '1', label: 'Hôm nay' },
            { value: '7', label: '7 ngày qua' },
            { value: '30', label: '30 ngày qua' },
            { value: '365', label: '1 năm qua' }
          ]}
        />
      </div>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card size="small" bordered={false} style={{ background: '#f0f2f5' }}>
            <Statistic title="Tổng Cảnh Báo" value={stats.total} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" bordered={false} style={{ background: '#f0f2f5' }}>
            <Statistic title="Số Cảnh Báo Đã Giải Quyết" value={stats.resolvedCount} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" bordered={false} style={{ background: '#f0f2f5' }}>
            <Statistic title="Lượt Tình Nguyện" value={stats.totalVolunteers} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="Phân Bố Loại Sự Cố" size="small" bordered={false}>
            <div style={{ height: 250, display: 'flex', justifyContent: 'center' }}>
                <PieChart width={300} height={250}>
                  <Pie
                    data={stats.typeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {stats.typeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[entry.type]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
            </div>
          </Card>
        </Col>
        
        <Col span={12}>
          <Card title="Xu Hướng" size="small" bordered={false}>
            <div style={{ height: 250, display: 'flex', justifyContent: 'center' }}>
                <BarChart width={300} height={250} data={stats.trendData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" fontSize={11} />
                  <YAxis fontSize={11} />
                  <Tooltip />
                  <Bar dataKey="fire" stackId="a" fill={COLORS.fire} name="Cháy" />
                  <Bar dataKey="accident" stackId="a" fill={COLORS.accident} name="Tai Nạn" />
                  <Bar dataKey="congestion" stackId="a" fill={COLORS.congestion} name="Kẹt Xe" />
                </BarChart>
            </div>
          </Card>
        </Col>
      </Row>
    </Modal>
  );
}
