'use client';

import React from 'react';
import { useTheme } from '@/components/ThemeProvider';

interface SettingsModalProps {
    onClose: () => void;
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
    const { theme, setTheme } = useTheme();

    const themes = [
        { id: 'default', name: '極簡雪白 (Snow Minimal)', bg: '#ffffff', primary: '#2563eb' },
        { id: 'vanilla', name: '溫潤米白 (Vanilla Cream)', bg: '#fdfbf7', primary: '#8b5a2b' },
        { id: 'silver', name: '俐落銀灰 (Silver Steel)', bg: '#f1f5f9', primary: '#0ea5e9' },
        { id: 'slate', name: '深邃湛藍 (Slate & Indigo)', bg: '#0f172a', primary: '#6366f1' },
        { id: 'ocean', name: '海洋深藍 (Deep Blue Ocean)', bg: '#11182a', primary: '#3b82f6' },
        { id: 'gold', name: '奢華黑金 (Luxury Charcoal)', bg: '#141414', primary: '#f59e0b' },
        { id: 'forest', name: '靜謐幽綠 (Serene Forest)', bg: '#132a24', primary: '#34d399' },
        { id: 'purple', name: '夢幻粉紫 (Dreamy Purple)', bg: '#332d41', primary: '#f472b6' },
    ] as const;

    return (
        <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, backdropFilter: 'blur(4px)'
        }} onClick={onClose}>
            <div className="card-glass" style={{ maxWidth: '450px', width: '90%', padding: '32px' }} onClick={e => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>⚙️ 系統設定</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
                </div>

                <div style={{ marginBottom: '24px' }}>
                    <h4 style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>外觀主題</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {themes.map((t) => (
                            <button
                                key={t.id}
                                onClick={() => setTheme(t.id as any)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    padding: '12px 16px',
                                    borderRadius: '12px',
                                    background: theme === t.id ? 'var(--color-bg-card-hover)' : 'var(--color-bg-secondary)',
                                    border: `1px solid ${theme === t.id ? 'var(--color-primary)' : 'var(--color-border)'}`,
                                    cursor: 'pointer',
                                    transition: 'all 0.2s ease',
                                    color: 'var(--color-text-primary)'
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
                                    <div style={{
                                        width: '24px', height: '24px', borderRadius: '50%',
                                        background: t.bg, border: `2px solid ${t.primary}`,
                                        boxShadow: theme === t.id ? `0 0 10px ${t.primary}55` : 'none',
                                        flexShrink: 0
                                    }} />
                                    <span style={{
                                        fontWeight: theme === t.id ? 600 : 400,
                                        textAlign: 'left',
                                        lineHeight: '1.4'
                                    }}>{t.name}</span>
                                </div>
                                {theme === t.id && (
                                    <span style={{ color: 'var(--color-primary)', fontWeight: 600 }}>✓</span>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '32px' }}>
                    <button className="btn-primary" onClick={onClose} style={{ width: '100%' }}>完成</button>
                </div>
            </div>
        </div>
    );
}
