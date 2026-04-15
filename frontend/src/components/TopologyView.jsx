import React, { useEffect, useMemo, useState } from 'react';
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useStore } from '../store/mainStore';
import EndpointNode from './EndpointNode';
import { Handle, Position } from '@xyflow/react';

// Custom KVM Switch central node
const KVMSwitchNode = ({ data }) => {
    return (
        <div style={{
            padding: '20px 30px',
            background: 'var(--accent)',
            color: '#fff',
            borderRadius: '12px',
            fontWeight: 'bold',
            border: '2px solid rgba(255,255,255,0.2)',
            boxShadow: '0 0 20px var(--accent-glow)'
        }}>
            {data.label}
            <Handle type="source" position={Position.Bottom} style={{ background: '#fff', border: 'none' }} />
        </div>
    )
};

const nodeTypes = {
    endpoint: EndpointNode,
    kvmSwitch: KVMSwitchNode
};

const TopologyView = () => {
    const { topology, selectedDeviceId, fetchTopology } = useStore();
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    useEffect(() => {
        if (selectedDeviceId) {
            fetchTopology(selectedDeviceId);
        }
    }, [selectedDeviceId]);

    useEffect(() => {
        if (topology && topology.nodes && topology.edges) {
            // Calculate Radial Layout
            const centerX = 300;
            const centerY = 150;
            const radius = 250;

            const endNodes = topology.nodes.filter(n => n.type === 'endpoint');
            const switchNodeIndex = topology.nodes.findIndex(n => n.type === 'kvmSwitch');

            const laidOutNodes = topology.nodes.map((node) => {
                if (node.type === 'kvmSwitch') {
                    return { ...node, position: { x: centerX, y: centerY } };
                } else {
                    // Find index among endpoints to distribute in an arc
                    const epIdx = endNodes.findIndex(e => e.id === node.id);
                    const totalEps = endNodes.length || 1;
                    // Distribute across a half-circle below the switch
                    const angle = Math.PI - (epIdx / Math.max(1, totalEps - 1)) * Math.PI;

                    return {
                        ...node,
                        position: {
                            x: centerX + radius * Math.cos(angle),
                            y: centerY + 100 + radius * Math.sin(angle)
                        }
                    };
                }
            });

            setNodes(laidOutNodes);
            setEdges(topology.edges);
        }
    }, [topology, setNodes, setEdges]);

    if (!selectedDeviceId) return <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>Select a Device</div>;
    if (!topology) return <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>Loading Topology...</div>;

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                nodeTypes={nodeTypes}
                fitView
            >
                <Controls style={{ background: 'var(--bg-secondary)', fill: 'var(--text-primary)' }} />
                <Background color="var(--border)" gap={20} />
            </ReactFlow>
        </div>
    );
};

export default TopologyView;
