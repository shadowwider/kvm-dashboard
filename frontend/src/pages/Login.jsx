import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import api from '../utils/api';
import './Login.css';

const Login = () => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const login = useAuthStore((state) => state.login);
    const navigate = useNavigate();

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const response = await api.post('/auth/login', formData, {
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
            });

            const { access_token } = response.data;

            // Get user info
            const userRes = await api.get('/auth/me', {
                headers: { Authorization: `Bearer ${access_token}` }
            });

            login(access_token, userRes.data);
            navigate('/dashboard');
        } catch (err) {
            const detail = err.response?.data?.detail;
            setError(typeof detail === 'string' ? detail : '登录失败，请检查用户名和密码。');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-background">
                <div className="particle particle-1"></div>
                <div className="particle particle-2"></div>
                <div className="particle particle-3"></div>
            </div>
            <div className="glass-card login-card">
                <div className="login-header">
                    <h2>KVM 监控中心</h2>
                    <p>请登录以访问监控大屏</p>
                </div>
                <form onSubmit={handleLogin} className="login-form">
                    <div className="input-group">
                        <label>用户名</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            placeholder="请输入用户名"
                        />
                    </div>
                    <div className="input-group">
                        <label>密码</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            placeholder="请输入密码"
                        />
                    </div>
                    {error && <div className="error-message">{error}</div>}
                    <button type="submit" disabled={loading} className="login-button">
                        {loading ? '验证中...' : '登 录'}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Login;
