'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import apiClient from '@/lib/api-client';
import type { PositionDetail, MarketDetail } from '@/lib/api-client';

interface PositionTableProps {
    positions: PositionDetail[];
    onQuickTrade?: (position: PositionDetail, action: 'buy' | 'sell') => void;
    onEdit?: (position: PositionDetail) => void;
}

type SortColumn = 'symbol' | 'current_price' | 'total_quantity' | 'avg_cost' | 'total_value' | 'unrealized_pnl' | 'unrealized_pnl_pct' | 'price_change_24h_pct';
type SortDirection = 'asc' | 'desc';

const CATEGORY_ICONS: Record<string, string> = {
    tw_stock: '🇹🇼',
    us_stock: '🇺🇸',
    crypto: '₿',
    fiat: '💵',
    liability: '💳',
};

export default function PositionTable({ positions, onQuickTrade, onEdit }: PositionTableProps) {
    const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});
    const prevPricesRef = useRef<Record<string, number>>({});
    const [sortColumn, setSortColumn] = useState<SortColumn>('total_value');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [marketDetailCache, setMarketDetailCache] = useState<Record<string, MarketDetail | 'loading'>>({});

    // 展開時 lazy-load 市場詳情
    const loadMarketDetail = useCallback(async (symbol: string, categorySlug: string) => {
        if (marketDetailCache[symbol]) return; // 已載入或載入中
        setMarketDetailCache(prev => ({ ...prev, [symbol]: 'loading' }));
        try {
            const res = await apiClient.getMarketDetail(symbol, categorySlug);
            if (res.data) {
                setMarketDetailCache(prev => ({ ...prev, [symbol]: res.data! }));
            }
        } catch {
            setMarketDetailCache(prev => { const n = { ...prev }; delete n[symbol]; return n; });
        }
    }, [marketDetailCache]);

    // 計算總資產用於占比條 (修復：使用換算後的基準幣別價值)
    const totalAssets = useMemo(() =>
        positions.reduce((sum, pos) => sum + Math.max(0, Number(pos.total_value_base || pos.total_value)), 0),
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

    const renderSortIcon = (column: SortColumn) => {
        if (sortColumn !== column) return null;
        return <span style={{ marginLeft: '4px', fontSize: '0.7rem' }}>{sortDirection === 'asc' ? '▲' : '▼'}</span>;
    };

    const sortedPositions = useMemo(() => {
        return [...positions].sort((a, b) => {
            let valA: number | string = 0;
            let valB: number | string = 0;

            // 針對需要跨幣別基準值的排序進行映射
            const getSortValue = (pos: PositionDetail, col: SortColumn) => {
                if (col === 'total_value') return Number(pos.total_value_base || pos.total_value);
                if (col === 'unrealized_pnl') return Number(pos.unrealized_pnl_base || pos.unrealized_pnl);
                if (col === 'current_price') return Number(pos.current_price_base || pos.current_price);
                return col === 'symbol' ? pos.symbol : Number(pos[col] || 0);
            };

            valA = getSortValue(a, sortColumn);
            valB = getSortValue(b, sortColumn);

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
                            <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer', width: '20%', whiteSpace: 'nowrap' }}>標的 {renderSortIcon('symbol')}</th>
                            <th onClick={() => handleSort('current_price')} style={{ textAlign: 'right', cursor: 'pointer', whiteSpace: 'nowrap' }}>價格 / 成本 {renderSortIcon('current_price')}</th>
                            <th onClick={() => handleSort('total_value')} style={{ textAlign: 'right', cursor: 'pointer', whiteSpace: 'nowrap' }}>市值 / 數量 {renderSortIcon('total_value')}</th>
                            <th onClick={() => handleSort('unrealized_pnl')} style={{ textAlign: 'right', cursor: 'pointer', whiteSpace: 'nowrap' }}>損益 {renderSortIcon('unrealized_pnl')}</th>
                            <th onClick={() => handleSort('unrealized_pnl_pct')} style={{ textAlign: 'right', cursor: 'pointer', whiteSpace: 'nowrap' }}>報酬 {renderSortIcon('unrealized_pnl_pct')}</th>
                            <th onClick={() => handleSort('price_change_24h_pct')} style={{ textAlign: 'right', width: '110px', cursor: 'pointer', whiteSpace: 'nowrap' }}>
                                <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                                    24H 漲跌 {renderSortIcon('price_change_24h_pct')}
                                </div>
                            </th>
                            <th style={{ textAlign: 'center', width: '80px' }}>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedPositions.map((pos) => {
                            const pnl = Number(pos.unrealized_pnl);
                            const pnlPct = Number(pos.unrealized_pnl_pct);
                            const change24h = pos.price_change_24h_pct;
                            const isProfit = pnl >= 0;
                            const flash = flashMap[pos.symbol];
                            const isExpanded = expandedId === pos.symbol;
                            const weight = totalAssets > 0 ? (Number(pos.total_value_base || pos.total_value) / totalAssets) * 100 : 0;

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
                                            {/* 占比視覺條 + 百分比數字 */}
                                            <div style={{
                                                marginTop: '6px', display: 'flex', alignItems: 'center', gap: '6px'
                                            }}>
                                                <div style={{
                                                    width: '50px', height: '5px',
                                                    background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden'
                                                }}>
                                                    <div style={{
                                                        width: `${Math.min(100, Math.max(0, weight))}%`, height: '100%',
                                                        background: 'var(--color-primary)', borderRadius: '3px'
                                                    }} />
                                                </div>
                                                <span style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                                                    {weight.toFixed(1)}%
                                                </span>
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

                                        {/* 欄位 D: 損益 */}
                                        <td style={{ textAlign: 'right' }}>
                                            <div className={`number ${isProfit ? 'pnl-positive' : 'pnl-negative'}`} style={{ fontWeight: 600 }}>
                                                {isProfit ? '+' : ''}{formatCurrency(pnl, pos.category_slug)}
                                            </div>
                                        </td>

                                        {/* 欄位 E: 報酬 */}
                                        <td style={{ textAlign: 'right' }}>
                                            <span className={isProfit ? 'pnl-badge-positive' : 'pnl-badge-negative'} style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                                                {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                                            </span>
                                        </td>

                                        {/* 欄位 F: 24h 漲跌 */}
                                        <td style={{ textAlign: 'right' }}>
                                            {change24h !== undefined && change24h !== null ? (
                                                <div className={`number ${change24h >= 0 ? 'pnl-positive' : 'pnl-negative'}`} style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                                    {change24h > 0 ? '▲' : change24h < 0 ? '▼' : ''}
                                                    {Math.abs(change24h).toFixed(2)}%
                                                </div>
                                            ) : (
                                                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>--</span>
                                            )}
                                        </td>

                                        {/* 欄位 G: 操作 */}
                                        <td onClick={(e) => e.stopPropagation()}>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                <button onClick={() => onQuickTrade?.(pos, 'buy')} style={actionBtnStyle('buy')}>加碼</button>
                                                <button onClick={() => onQuickTrade?.(pos, 'sell')} style={actionBtnStyle('sell')}>減碼</button>
                                                <button onClick={() => onEdit?.(pos)} style={actionBtnStyle('edit')}>編輯</button>
                                            </div>
                                        </td>
                                    </tr>

                                    {/* 詳情展開面板 */}
                                    {isExpanded && (() => {
                                        const md = marketDetailCache[pos.symbol];
                                        if (!md) loadMarketDetail(pos.symbol, pos.category_slug);
                                        const isLoading = !md || md === 'loading';
                                        const detail = (md && md !== 'loading') ? md : null;

                                        const changePills: { label: string; key: keyof MarketDetail }[] = [
                                            { label: '24小時', key: 'change_pct_24h' },
                                            { label: '7天', key: 'change_pct_7d' },
                                            { label: '14天', key: 'change_pct_14d' },
                                            { label: '30天', key: 'change_pct_30d' },
                                            { label: '60天', key: 'change_pct_60d' },
                                            { label: '1年', key: 'change_pct_1y' },
                                        ];

                                        const formatLargeNum = (num: number | undefined | null, categorySlug: string) => {
                                            if (num == null) return '--';
                                            const symbol = (categorySlug === 'us_stock' || categorySlug === 'crypto') ? '$' : 'NT$ ';

                                            let formatted = '';
                                            if (num >= 1e12) formatted = `${(num / 1e12).toFixed(2)}T`;
                                            else if (num >= 1e9) formatted = `${(num / 1e9).toFixed(2)}B`;
                                            else if (num >= 1e6) formatted = `${(num / 1e6).toFixed(2)}M`;
                                            else formatted = num.toLocaleString();

                                            return `${symbol}${formatted}`;
                                        };

                                        return (
                                            <tr>
                                                <td colSpan={7} style={{ padding: '0', background: 'var(--color-bg-secondary)' }}>
                                                    <div style={{ padding: '20px 24px', animation: 'fadeIn 0.3s ease' }}>
                                                        {isLoading ? (
                                                            <div style={{ textAlign: 'center', padding: '16px', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                                                                ⏳ 載入市場數據...
                                                            </div>
                                                        ) : (
                                                            <div style={{ width: '100%' }}>
                                                                {/* 區間漲跌 - 表格式 */}
                                                                <div style={{ marginBottom: '16px' }}>
                                                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0', borderRadius: '10px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
                                                                        {changePills.map((pill, i) => {
                                                                            const val = detail?.[pill.key] as number | undefined;
                                                                            const isPositive = val != null && val >= 0;
                                                                            const color = val == null ? 'var(--color-text-muted)' : isPositive ? '#22c55e' : '#ef4444';
                                                                            return (
                                                                                <div key={pill.key} style={{
                                                                                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                                                                                    padding: '12px 8px',
                                                                                    background: 'rgba(255,255,255,0.02)',
                                                                                    borderRight: i < 5 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                                                                                }}>
                                                                                    <span style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)', marginBottom: '6px', fontWeight: 500 }}>{pill.label}</span>
                                                                                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>
                                                                                        {val != null ? `${val > 0 ? '▲' : val < 0 ? '▼' : ''}${Math.abs(val).toFixed(1)}%` : '--'}
                                                                                    </span>
                                                                                </div>
                                                                            );
                                                                        })}
                                                                    </div>
                                                                </div>

                                                                {/* 市場概況 - 同樣撐滿 */}
                                                                {(detail?.market_cap != null || detail?.week_52_high != null || detail?.pe_ratio != null) && (() => {
                                                                    const stats: { label: string; value: string; color?: string }[] = [];
                                                                    if (detail?.market_cap != null) stats.push({ label: '市值', value: formatLargeNum(detail.market_cap, pos.category_slug) });
                                                                    if (detail?.week_52_high != null) stats.push({ label: '52W High', value: formatCurrency(detail.week_52_high, pos.category_slug), color: '#22c55e' });
                                                                    if (detail?.week_52_low != null) stats.push({ label: '52W Low', value: formatCurrency(detail.week_52_low, pos.category_slug), color: '#ef4444' });
                                                                    if (detail?.pe_ratio != null) stats.push({ label: 'P/E', value: detail.pe_ratio.toFixed(2) });
                                                                    return (
                                                                        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${stats.length}, 1fr)`, gap: '0', borderRadius: '10px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
                                                                            {stats.map((stat, i) => (
                                                                                <div key={stat.label} style={{
                                                                                    display: 'flex', flexDirection: 'column', alignItems: 'center',
                                                                                    padding: '12px 8px',
                                                                                    background: 'rgba(255,255,255,0.02)',
                                                                                    borderRight: i < stats.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                                                                                }}>
                                                                                    <span style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)', marginBottom: '6px', fontWeight: 500 }}>{stat.label}</span>
                                                                                    <span style={{ fontSize: '0.85rem', fontWeight: 700, color: stat.color || 'var(--color-text-primary)', fontFamily: 'var(--font-mono)' }}>
                                                                                        {stat.value}
                                                                                    </span>
                                                                                </div>
                                                                            ))}
                                                                        </div>
                                                                    );
                                                                })()}
                                                            </div>
                                                        )}
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })()}
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

const ACTION_BTN_COLORS = {
    buy: { border: 'rgba(34, 197, 94, 0.3)', bg: 'rgba(34, 197, 94, 0.1)', text: '#22c55e' },
    sell: { border: 'rgba(239, 68, 68, 0.3)', bg: 'rgba(239, 68, 68, 0.1)', text: '#ef4444' },
    edit: { border: 'rgba(99, 102, 241, 0.3)', bg: 'rgba(99, 102, 241, 0.1)', text: '#818cf8' },
} as const;

const actionBtnStyle = (type: 'buy' | 'sell' | 'edit') => ({
    padding: '2px 8px',
    borderRadius: '4px',
    border: '1px solid',
    borderColor: ACTION_BTN_COLORS[type].border,
    background: ACTION_BTN_COLORS[type].bg,
    color: ACTION_BTN_COLORS[type].text,
    cursor: 'pointer',
    fontSize: '0.7rem',
    fontWeight: 600,
});

const statCardStyle: React.CSSProperties = {
    padding: '10px 16px', borderRadius: '8px',
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
};

const statLabelStyle: React.CSSProperties = {
    fontSize: '0.65rem', color: 'var(--color-text-muted)', fontWeight: 500,
};

const statValueStyle: React.CSSProperties = {
    fontSize: '0.9rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
};

export const CATEGORY_IDS: Record<string, number> = {
    tw_stock: 1,
    us_stock: 2,
    crypto: 3,
    fiat: 4,
    liability: 5,
};
