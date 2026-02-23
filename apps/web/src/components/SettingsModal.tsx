'use client';

import React from 'react';
import { useTheme } from '@/components/ThemeProvider';

interface SettingsModalProps {
    onClose: () => void;
}

export default function SettingsModal({ onClose }: SettingsModalProps) {
    const { theme, setTheme } = useTheme();

    const themes = [
        { id: 'default', name: '湛藍 (Slate & Indigo)', bg: '#0f172a', primary: '#6366f1' },
        { id: 'obsidian', name: '黑曜 (Onyx & Zinc)', bg: '#000000', primary: '#fafafa' },
        { id: 'forest', name: '蒼翠 (Emerald & Neutral)', bg: '#0a0a0a', primary: '#10b981' },
        { id: 'cyber', name: '暮紫 (Violet & Slate)', bg: '#0b0415', primary: '#8b5cf6' },
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
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <div style={{
                                        width: '24px', height: '24px', borderRadius: '50%',
                                        background: t.bg, border: `2px solid ${t.primary}`,
                                        boxShadow: theme === t.id ? `0 0 10px ${t.primary}55` : 'none'
                                    }} />
                                    <span style={{ fontWeight: theme === t.id ? 600 : 400 }}>{t.name}</span>
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
