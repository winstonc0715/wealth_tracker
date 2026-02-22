'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import apiClient from '@/lib/api-client';

export default function LoginPage() {
    const router = useRouter();
    const [isRegister, setIsRegister] = useState(false);
    const [email, setEmail] = useState('');
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isRegister) {
                await apiClient.register(email, username, password);
                await apiClient.login(email, password);
            } else {
                await apiClient.login(email, password);
            }
            router.push('/dashboard');
        } catch (err) {
            setError((err as Error).message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #0a0a1a 0%, #111128 50%, #1a103a 100%)',
            padding: '20px',
        }}>
            {/* 背景裝飾 */}
            <div style={{
                position: 'fixed',
                top: '-50%',
                right: '-20%',
                width: '600px',
                height: '600px',
                background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%)',
                borderRadius: '50%',
                pointerEvents: 'none',
            }} />
            <div style={{
                position: 'fixed',
                bottom: '-30%',
                left: '-10%',
                width: '500px',
                height: '500px',
                background: 'radial-gradient(circle, rgba(139,92,246,0.1) 0%, transparent 70%)',
                borderRadius: '50%',
                pointerEvents: 'none',
            }} />

            <div className="card-glass" style={{
                width: '100%',
                maxWidth: '440px',
                textAlign: 'center',
            }}>
                {/* Logo */}
                <div style={{ marginBottom: '32px' }}>
                    <div style={{
                        fontSize: '2.5rem',
                        fontWeight: 800,
                        background: 'linear-gradient(135deg, #6366f1, #a855f7, #6366f1)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        letterSpacing: '-0.02em',
                    }}>
                        WealthTracker
                    </div>
                    <p style={{
                        color: 'var(--color-text-muted)',
                        marginTop: '8px',
                        fontSize: '0.95rem',
                    }}>
                        跨平台資產管理系統
                    </p>
                </div>

                {/* Tab 切換 */}
                <div style={{
                    display: 'flex',
                    gap: '4px',
                    background: 'var(--color-bg-primary)',
                    borderRadius: '10px',
                    padding: '4px',
                    marginBottom: '24px',
                }}>
                    <button
                        onClick={() => setIsRegister(false)}
                        style={{
                            flex: 1,
                            padding: '10px',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: 600,
                            fontSize: '0.9rem',
                            transition: 'all 0.2s',
                            background: !isRegister ? 'var(--color-primary)' : 'transparent',
                            color: !isRegister ? 'white' : 'var(--color-text-muted)',
                        }}
                    >
                        登入
                    </button>
                    <button
                        onClick={() => setIsRegister(true)}
                        style={{
                            flex: 1,
                            padding: '10px',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: 'pointer',
                            fontWeight: 600,
                            fontSize: '0.9rem',
                            transition: 'all 0.2s',
                            background: isRegister ? 'var(--color-primary)' : 'transparent',
                            color: isRegister ? 'white' : 'var(--color-text-muted)',
                        }}
                    >
                        註冊
                    </button>
                </div>

                {/* 表單 */}
                <form onSubmit={handleSubmit}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <input
                            type="email"
                            placeholder="電子信箱"
                            className="input-field"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                        {isRegister && (
                            <input
                                type="text"
                                placeholder="使用者名稱"
                                className="input-field"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                            />
                        )}
                        <input
                            type="password"
                            placeholder="密碼"
                            className="input-field"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            minLength={6}
                        />
                    </div>

                    {error && (
                        <div style={{
                            marginTop: '16px',
                            padding: '10px 16px',
                            background: 'var(--color-loss-bg)',
                            color: 'var(--color-loss)',
                            borderRadius: '8px',
                            fontSize: '0.9rem',
                        }}>
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="btn-primary"
                        disabled={loading}
                        style={{
                            width: '100%',
                            marginTop: '24px',
                            padding: '14px',
                            fontSize: '1rem',
                            opacity: loading ? 0.7 : 1,
                        }}
                    >
                        {loading ? '處理中...' : isRegister ? '建立帳號' : '登入'}
                    </button>
                </form>
            </div>
        </div>
    );
}
