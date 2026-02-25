'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import type { PositionDetail } from '@/lib/api-client';

interface PositionTableProps {
    positions: PositionDetail[];
    onQuickTrade?: (position: PositionDetail, action: 'buy' | 'sell') => void;
}

type SortColumn = 'symbol' | 'current_price' | 'total_quantity' | 'avg_cost' | 'total_value' | 'unrealized_pnl' | 'unrealized_pnl_pct';
type SortDirection = 'asc' | 'desc';

const CATEGORY_ICONS: Record<string, string> = {
    tw_stock: '🇹🇼',
    us_stock: '🇺🇸',
    crypto: '₿',
    fiat: '💵',
    liability: '💳',
};

export default function PositionTable({ positions, onQuickTrade }: PositionTableProps) {
    const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});
    const prevPricesRef = useRef<Record<string, number>>({});
    const [sortColumn, setSortColumn] = useState<SortColumn>('total_value');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
    const [expandedId, setExpandedId] = useState<string | null>(null);

    // 計算總資產用於占比條
    const totalAssets = useMemo(() =>
        positions.reduce((sum, pos) => sum + Math.max(0, Number(pos.total_value)), 0),
        [positions]);

    useEffect(() => {
        const flashes: Record<string, 'up' | 'down'> = {};
        positions.forEach((pos) => {
            const prev = prevPricesRef.current[pos.symbol];
            if (prev !== undefined && prev !== Number(pos.current_price)) {
                flashes[pos.symbol] = Number(pos.current_price) > prev ? 'up' : 'down';
            }
            prevPricesRef.current[pos.symbol] = Number(pos.current_price);
        });

        if (Object.keys(flashes).length > 0) {
            setFlashMap(flashes);
            setTimeout(() => setFlashMap({}), 600);
        }
    }, [positions]);

    const formatCurrency = (value: number, categorySlug: string) => {
        const num = Math.abs(Number(value));
        const sign = value < 0 ? '-' : '';
        if (categorySlug === 'us_stock' || categorySlug === 'crypto') {
            return `${sign}$ ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }
        return `${sign}NT$ ${num.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    };

    const handleSort = (column: SortColumn) => {
        if (sortColumn === column) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(column);
            setSortDirection('desc');
        }
    };

    const sortedPositions = useMemo(() => {
        return [...positions].sort((a, b) => {
            let valA: number | string = 0;
            let valB: number | string = 0;
            if (sortColumn === 'symbol') {
                valA = a.symbol;
                valB = b.symbol;
            } else {
                valA = Number(a[sortColumn] || 0);
                valB = Number(b[sortColumn] || 0);
            }
            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
        });
    }, [positions, sortColumn, sortDirection]);

    if (!positions || positions.length === 0) {
        return (
            <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>尚無持倉</p>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>持倉明細</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>點擊項目查看詳情</span>
            </div>

            <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ borderSpacing: 0 }}>
                    <thead>
                        <tr>
                            <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer', width: '30%' }}>標的</th>
                            <th onClick={() => handleSort('current_price')} style={{ textAlign: 'right', cursor: 'pointer' }}>價格 / 成本</th>
                            <th onClick={() => handleSort('total_value')} style={{ textAlign: 'right', cursor: 'pointer' }}>市值 / 數量</th>
                            <th onClick={() => handleSort('unrealized_pnl')} style={{ textAlign: 'right', cursor: 'pointer' }}>損益 / 報酬</th>
                            <th style={{ textAlign: 'center', width: '80px' }}>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedPositions.map((pos) => {
                            const pnl = Number(pos.unrealized_pnl);
                            const pnlPct = Number(pos.unrealized_pnl_pct);
                            const isProfit = pnl >= 0;
                            const flash = flashMap[pos.symbol];
                            const isExpanded = expandedId === pos.symbol;
                            const weight = totalAssets > 0 ? (Number(pos.total_value) / totalAssets) * 100 : 0;

                            // 熱度背景色 (更淡的視覺)
                            let heatStyle = {};
                            if (pnlPct > 20) heatStyle = { background: 'linear-gradient(90deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%)' };
                            else if (pnlPct < -20) heatStyle = { background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.05) 0%, transparent 100%)' };

                            return (
                                <React.Fragment key={pos.symbol}>
                                    <tr
                                        onClick={() => setExpandedId(isExpanded ? null : pos.symbol)}
                                        style={{
                                            cursor: 'pointer',
                                            ...heatStyle,
                                            borderLeft: isExpanded ? '4px solid var(--color-primary)' : '4px solid transparent',
                                            transition: 'all 0.2s',
                                            backgroundColor: isExpanded ? 'var(--color-bg-card-hover)' : 'transparent'
                                        }}
                                    >
                                        {/* 欄位 A: 資產資訊 */}
                                        <td style={{ paddingRight: '0' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <span style={{ fontSize: '1.2rem' }}>{CATEGORY_ICONS[pos.category_slug] || '📊'}</span>
                                                <div style={{ overflow: 'hidden' }}>
                                                    <div style={{ fontWeight: 700, fontSize: '0.95rem', whiteSpace: 'nowrap' }}>{pos.symbol}</div>
                                                    <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                        {pos.name || pos.category_slug}
                                                    </div>
                                                </div>
                                            </div>
                                            {/* 占比視覺條 */}
                                            <div style={{
                                                marginTop: '6px', width: '60px', height: '3px',
                                                background: 'var(--color-bg-secondary)', borderRadius: '2px', overflow: 'hidden'
                                            }}>
                                                <div style={{
                                                    width: `${Math.min(100, Math.max(0, weight))}%`, height: '100%',
                                                    background: 'var(--color-primary)', opacity: 0.7
                                                }} />
                                            </div>
                                        </td>

                                        {/* 欄位 B: 價格對比 */}
                                        <td style={{ textAlign: 'right' }}>
                                            <div className={`number ${flash === 'up' ? 'price-flash-up' : flash === 'down' ? 'price-flash-down' : ''}`}
                                                style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                                                {formatCurrency(Number(pos.current_price), pos.category_slug)}
                                            </div>
                                            <div className="number" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                                                ({formatCurrency(Number(pos.avg_cost), pos.category_slug)})
                                            </div>
                                        </td>

                                        {/* 欄位 C: 市值 / 數量 */}
                                        <td style={{ textAlign: 'right' }}>
                                            <div className="number" style={{ fontWeight: 600 }}>
                                                {formatCurrency(Number(pos.total_value), pos.category_slug)}
                                            </div>
                                            <div className="number" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                                                {Number(pos.total_quantity).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                                            </div>
                                        </td>

                                        {/* 欄位 D: 績效表現 */}
                                        <td style={{ textAlign: 'right' }}>
                                            <div className={`number ${isProfit ? 'pnl-positive' : 'pnl-negative'}`} style={{ fontWeight: 600 }}>
                                                {isProfit ? '+' : ''}{formatCurrency(pnl, pos.category_slug)}
                                            </div>
                                            <div style={{ marginTop: '2px' }}>
                                                <span className={isProfit ? 'pnl-badge-positive' : 'pnl-badge-negative'} style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                                                    {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                                                </span>
                                            </div>
                                        </td>

                                        {/* 欄位 E: 操作 */}
                                        <td onClick={(e) => e.stopPropagation()}>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                <button onClick={() => onQuickTrade?.(pos, 'buy')} style={actionBtnStyle('buy')}>加碼</button>
                                                <button onClick={() => onQuickTrade?.(pos, 'sell')} style={actionBtnStyle('sell')}>減碼</button>
                                            </div>
                                        </td>
                                    </tr>

                                    {/* 詳情展開面板 */}
                                    {isExpanded && (
                                        <tr>
                                            <td colSpan={5} style={{ padding: '0', background: 'var(--color-bg-secondary)' }}>
                                                <div style={{ padding: '20px 24px', animation: 'fadeIn 0.3s ease' }}>
                                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                                                        <div>
                                                            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>💡 資產分析</div>
                                                            <div style={{ fontSize: '0.9rem' }}>
                                                                此持倉佔總資產的 <span style={{ fontWeight: 600, color: 'var(--color-primary)' }}>{weight.toFixed(2)}%</span>。
                                                                目前的平均成本為 {formatCurrency(Number(pos.avg_cost), pos.category_slug)}。
                                                            </div>
                                                        </div>
                                                        <div style={{ textAlign: 'right' }}>
                                                            <button className="btn-secondary" style={{ fontSize: '0.8rem', padding: '6px 12px' }}>
                                                                查看交易歷史 →
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            <style jsx>{`
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(-10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    );
}

const actionBtnStyle = (type: 'buy' | 'sell') => ({
    padding: '2px 8px',
    borderRadius: '4px',
    border: '1px solid',
    borderColor: type === 'buy' ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)',
    background: type === 'buy' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
    color: type === 'buy' ? '#22c55e' : '#ef4444',
    cursor: 'pointer',
    fontSize: '0.7rem',
    fontWeight: 600,
});
