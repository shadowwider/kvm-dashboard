import React, { useEffect, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { useStore } from '../store/mainStore';
import api from '../utils/api';

const MetricChart = () => {
    const { selectedDeviceId } = useStore();
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!selectedDeviceId) return;

        const fetchHistory = async () => {
            setLoading(true);
            try {
                const res = await api.get(`/metrics/history?device_id=${selectedDeviceId}&oid_name=temperature&hours=24`);
                setData(res.data);
            } catch (e) {
                console.error('Failed to fetch metric history', e);
            } finally {
                setLoading(false);
            }
        };

        fetchHistory();
    }, [selectedDeviceId]);

    if (!selectedDeviceId) {
        return <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>Select a device to view temperature history</div>;
    }

    const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        xAxis: {
            type: 'category',
            data: data.map(item => new Date(item.time).toLocaleTimeString()),
            axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.3)' } },
            axisLabel: { color: '#94a3b8' } // 'var(--text-secondary)' cannot be parsed in canvas
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
            axisLabel: { color: '#94a3b8' } // var(--text-secondary)
        },
        series: [
            {
                data: data.map(item => item.value_num),
                type: 'line',
                smooth: true,
                itemStyle: { color: '#6366f1' }, // var(--accent)
                areaStyle: {
                    color: {
                        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [{ offset: 0, color: 'rgba(99, 102, 241, 0.4)' }, { offset: 1, color: 'rgba(99, 102, 241, 0)' }]
                    }
                }
            }
        ],
        grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true }
    };

    return (
        <div style={{ width: '100%', height: '100%', padding: '10px' }}>
            {loading && data.length === 0 ? (
                <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>Loading Chart...</div>
            ) : (
                <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
            )}
        </div>
    );
};

export default MetricChart;
