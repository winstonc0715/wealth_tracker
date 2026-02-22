'use client';

/**
 * 資產配置圓餅圖
 *
 * 使用 Recharts PieChart 繪製各類別資產佔比。
 */

import {
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Tooltip,
} from 'recharts';
import type { AllocationItem } from '@/lib/api-client';
import { usePortfolioStore } from '@/stores/portfolio-store';

interface AllocationPieProps {
    data: AllocationItem[];
    totalValue: number;
}

const DEFAULT_COLORS = ['#6366f1', '#8b5cf6', '#f59e0b', '#22c55e', '#ef4444', '#3b82f6'];

export default function AllocationPie({ data, totalValue }: AllocationPieProps) {
    const { displayCurrency, exchangeRate } = usePortfolioStore();

    if (!data || data.length === 0) {
        return (
            <div className="card" style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--color-text-muted)' }}>暫無資產配置資料</p>
            </div>
        );
    }

    const chartData = data.map((item, index) => ({
        name: item.category,
        value: Number(item.value),
        percentage: Number(item.percentage),
        color: item.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
    }));

    const formattedTotalValue = displayCurrency === 'USD'
        ? `$ ${(totalValue / exchangeRate).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : `NT$ ${totalValue.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

    const tooltipFormatter = (value: number, name: string) => {
        const val = displayCurrency === 'USD'
            ? `$ ${(value / exchangeRate).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            : `NT$ ${value.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
        return [val, name];
    };

    return (
        <div className="card">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px' }}>
                資產配置
            </h3>

            {/* 總資產 */}
            <div style={{ textAlign: 'center', marginBottom: '8px' }}>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                    總資產
                </span>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>
                    {formattedTotalValue}
                </div>
            </div>

            <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                    <Pie
                        data={chartData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={85}
                        paddingAngle={3}
                        dataKey="value"
                        strokeWidth={0}
                    >
                        {chartData.map((entry, index) => (
                            <Cell key={index} fill={entry.color} />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={{
                            background: 'var(--color-bg-card)',
                            border: '1px solid var(--color-border)',
                            borderRadius: '10px',
                            boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                        }}
                        formatter={tooltipFormatter}
                    />
                </PieChart>
            </ResponsiveContainer>

            {/* 圖例列表 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                {chartData.map((item, index) => (
                    <div key={index} style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '6px 0',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{
                                width: '10px',
                                height: '10px',
                                borderRadius: '3px',
                                background: item.color,
                            }} />
                            <span style={{ fontSize: '0.9rem' }}>{item.name}</span>
                        </div>
                        <span style={{
                            fontFamily: "'JetBrains Mono', monospace",
                            fontSize: '0.9rem',
                            color: 'var(--color-text-secondary)',
                        }}>
                            {item.percentage.toFixed(1)}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
