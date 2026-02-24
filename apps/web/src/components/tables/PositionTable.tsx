'use client';

/**
 * 持倉明細表格
 *
 * 表格展示各標的的當前價格、持有數量、平均成本、
 * 總價值與未實現損益，每列有快速加碼/減碼按鈕。
 */

import { useState, useEffect, useRef, useMemo } from 'react';
import type { PositionDetail } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';

interface PositionTableProps {
    positions: PositionDetail[];
    onQuickTrade?: (position: PositionDetail, action: 'buy' | 'sell') => void;
}

type SortColumn = 'symbol' | 'current_price' | 'total_quantity' | 'avg_cost' | 'total_value' | 'unrealized_pnl' | 'unrealized_pnl_pct';
type SortDirection = 'asc' | 'desc';

// 資產類別圖標
const CATEGORY_ICONS: Record<string, string> = {
    tw_stock: '🇹🇼',
    us_stock: '🇺🇸',
    crypto: '₿',
    fiat: '💵',
    liability: '💳',
};

const CATEGORY_IDS: Record<string, number> = {
    tw_stock: 1,
    us_stock: 2,
    crypto: 3,
    fiat: 4,
    liability: 5,
};

export default function PositionTable({ positions, onQuickTrade }: PositionTableProps) {
    // 追蹤價格變化以觸發閃爍動畫
    const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});
    const prevPricesRef = useRef<Record<string, number>>({});

    // 排序狀態
    const [sortColumn, setSortColumn] = useState<SortColumn>('total_value');
    const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

    // 從 Store 取得狀態
    //（此處已不需要 exchangeRate，因為後端傳回的即為原幣格式）

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
        const num = Number(value);

        // 美股、加密貨幣以 USD 顯示 (後端已回傳原幣數值)
        if (categorySlug === 'us_stock' || categorySlug === 'crypto') {
            return `$ ${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        }

        return `NT$ ${num.toLocaleString('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    const handleSort = (column: SortColumn) => {
        if (sortColumn === column) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(column);
            setSortDirection('desc'); // 預設新欄位用降冪排序，較直覺
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
    }, [positions, sortColumn, sortDirection]); // 匯率同部縮放不影響排序，不需要把 exchangeRate 加入 dependencies

    if (!positions || positions.length === 0) {
        return (
            <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>
                    尚無持倉，點擊上方「+ 新增交易」開始吧！
                </p>
            </div>
        );
    }

    return (
        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>持倉明細</h3>
            </div>
            <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                    <thead>
                        <tr>
                            <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer' }}>
                                標的 {sortColumn === 'symbol' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('current_price')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                現價 {sortColumn === 'current_price' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('total_quantity')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                持有數量 {sortColumn === 'total_quantity' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('avg_cost')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                平均成本 {sortColumn === 'avg_cost' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('total_value')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                市值 {sortColumn === 'total_value' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('unrealized_pnl')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                損益 {sortColumn === 'unrealized_pnl' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th onClick={() => handleSort('unrealized_pnl_pct')} style={{ textAlign: 'right', cursor: 'pointer' }}>
                                報酬率 {sortColumn === 'unrealized_pnl_pct' && (sortDirection === 'asc' ? '↑' : '↓')}
                            </th>
                            <th style={{ textAlign: 'center' }}>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedPositions.map((pos) => {
                            const pnl = Number(pos.unrealized_pnl);
                            const pnlPct = Number(pos.unrealized_pnl_pct);
                            const isProfit = pnl >= 0;
                            const flash = flashMap[pos.symbol];

                            return (
                                <tr key={pos.symbol}>
                                    {/* 標的 */}
                                    <td>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                            <span style={{ fontSize: '1.2rem' }}>
                                                {CATEGORY_ICONS[pos.category_slug] || '📊'}
                                            </span>
                                            <div>
                                                <div style={{ fontWeight: 600 }}>{pos.symbol}</div>
                                                <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                                                    {pos.name || pos.category_slug}
                                                </div>
                                            </div>
                                        </div>
                                    </td>

                                    {/* 現價 */}
                                    <td
                                        style={{ textAlign: 'right', whiteSpace: 'nowrap' }}
                                        className={`number ${flash === 'up' ? 'price-flash-up' : flash === 'down' ? 'price-flash-down' : ''}`}
                                    >
                                        {formatCurrency(Number(pos.current_price), pos.category_slug)}
                                    </td>

                                    {/* 持有數量 */}
                                    <td style={{ textAlign: 'right' }} className="number">
                                        {Number(pos.total_quantity).toLocaleString(undefined, {
                                            minimumFractionDigits: 0,
                                            maximumFractionDigits: 4,
                                        })}
                                    </td>

                                    {/* 平均成本 */}
                                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }} className="number">
                                        {formatCurrency(Number(pos.avg_cost), pos.category_slug)}
                                    </td>

                                    {/* 市值 */}
                                    <td style={{ textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap' }} className="number">
                                        {formatCurrency(Number(pos.total_value), pos.category_slug)}
                                    </td>

                                    {/* 損益 */}
                                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                                        <span className={`number ${isProfit ? 'pnl-positive' : 'pnl-negative'}`}>
                                            {isProfit ? '+' : ''}{formatCurrency(pnl, pos.category_slug)}
                                        </span>
                                    </td>

                                    {/* 報酬率 */}
                                    <td style={{ textAlign: 'right' }}>
                                        <span className={isProfit ? 'pnl-badge-positive' : 'pnl-badge-negative'}>
                                            {isProfit ? '+' : ''}{pnlPct.toFixed(2)}%
                                        </span>
                                    </td>

                                    {/* 操作按鈕 */}
                                    <td style={{ textAlign: 'center' }}>
                                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                                            <button
                                                onClick={() => onQuickTrade?.(pos, 'buy')}
                                                style={{
                                                    padding: '4px 10px',
                                                    borderRadius: '6px',
                                                    border: '1px solid rgba(34, 197, 94, 0.3)',
                                                    background: 'rgba(34, 197, 94, 0.1)',
                                                    color: '#22c55e',
                                                    cursor: 'pointer',
                                                    fontSize: '0.8rem',
                                                    fontWeight: 600,
                                                    transition: 'all 0.2s',
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.currentTarget.style.background = 'rgba(34, 197, 94, 0.2)';
                                                    e.currentTarget.style.borderColor = '#22c55e';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.currentTarget.style.background = 'rgba(34, 197, 94, 0.1)';
                                                    e.currentTarget.style.borderColor = 'rgba(34, 197, 94, 0.3)';
                                                }}
                                            >
                                                + 加碼
                                            </button>
                                            <button
                                                onClick={() => onQuickTrade?.(pos, 'sell')}
                                                style={{
                                                    padding: '4px 10px',
                                                    borderRadius: '6px',
                                                    border: '1px solid rgba(239, 68, 68, 0.3)',
                                                    background: 'rgba(239, 68, 68, 0.1)',
                                                    color: '#ef4444',
                                                    cursor: 'pointer',
                                                    fontSize: '0.8rem',
                                                    fontWeight: 600,
                                                    transition: 'all 0.2s',
                                                }}
                                                onMouseEnter={(e) => {
                                                    e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                                                    e.currentTarget.style.borderColor = '#ef4444';
                                                }}
                                                onMouseLeave={(e) => {
                                                    e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                                                    e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)';
                                                }}
                                            >
                                                − 減碼
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

export { CATEGORY_IDS };
