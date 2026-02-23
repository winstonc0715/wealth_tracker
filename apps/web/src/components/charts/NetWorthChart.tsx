'use client';

/**
 * 歷史淨值走勢圖（折線圖）
 *
 * 使用 Recharts 繪製互動式淨值趨勢圖。
 */

import { useState, useEffect } from 'react';
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from 'recharts';
import { usePortfolioStore } from '@/stores/portfolio-store';

interface NetWorthChartProps {
    data: { date: string; value: number }[];
}

const PERIOD_DAYS: Record<string, number> = {
    '1W': 7,
    '1M': 30,
    '3M': 90,
    '1Y': 365,
};

export default function NetWorthChart({ data }: NetWorthChartProps) {
    const { selectedPortfolio, fetchHistory, displayCurrency, exchangeRate } = usePortfolioStore();
    const [activePeriod, setActivePeriod] = useState('1M');

    const handlePeriodChange = (period: string) => {
        setActivePeriod(period);
        if (selectedPortfolio) {
            fetchHistory(selectedPortfolio.id, PERIOD_DAYS[period]);
        }
    };

    if (!data || data.length === 0) {
        return (
            <div className="card" style={{ height: '350px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <p style={{ color: 'var(--color-text-muted)' }}>暫無淨值歷史資料</p>
            </div>
        );
    }

    // 判斷趨勢（漲/跌）
    const isUp = data.length >= 2 && data[data.length - 1].value >= data[0].value;
    const lineColor = isUp ? '#22c55e' : '#ef4444';
    const gradientId = 'netWorthGradient';

    const formatCurrency = (value: number) => {
        let val = value;
        const prefix = displayCurrency === 'USD' ? '$' : '';
        if (displayCurrency === 'USD') val = val / exchangeRate;

        if (val >= 1000000) return `${prefix}${(val / 1000000).toFixed(1)}M`;
        if (val >= 1000) return `${prefix}${(val / 1000).toFixed(0)}K`;
        return `${prefix}${val.toLocaleString(displayCurrency === 'USD' ? 'en-US' : 'zh-TW', { maximumFractionDigits: 0 })}`;
    };

    const tooltipFormatter = (value: number) => {
        const val = displayCurrency === 'USD'
            ? `$ ${(value / exchangeRate).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            : `NT$ ${value.toLocaleString('zh-TW', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
        return [val, '淨值'];
    };

    return (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>淨值走勢</h3>
                <div style={{ display: 'flex', gap: '8px' }}>
                    {['1W', '1M', '3M', '1Y'].map((period) => (
                        <button
                            key={period}
                            className={activePeriod === period ? "btn-primary" : "btn-secondary"}
                            style={{
                                padding: '4px 12px',
                                fontSize: '0.8rem',
                                background: activePeriod === period ? 'var(--color-primary)' : 'rgba(42, 42, 90, 0.3)',
                                borderColor: activePeriod === period ? 'var(--color-primary)' : 'var(--color-border)',
                                color: activePeriod === period ? '#fff' : 'var(--color-text-secondary)',
                            }}
                            onClick={() => handlePeriodChange(period)}
                        >
                            {period}
                        </button>
                    ))}
                </div>
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
                        <defs>
                            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={lineColor} stopOpacity={0.3} />
                                <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(42, 42, 90, 0.5)"
                            vertical={false}
                        />
                        <XAxis
                            dataKey="date"
                            stroke="var(--color-text-muted)"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            stroke="var(--color-text-muted)"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={formatCurrency}
                        />
                        <Tooltip
                            contentStyle={{
                                background: 'var(--color-bg-card)',
                                border: '1px solid var(--color-border)',
                                borderRadius: '10px',
                                boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
                            }}
                            labelStyle={{ color: 'var(--color-text-secondary)' }}
                            formatter={tooltipFormatter}
                        />
                        <Area
                            type="monotone"
                            dataKey="value"
                            stroke={lineColor}
                            strokeWidth={2}
                            fill={`url(#${gradientId})`}
                            dot={false}
                            activeDot={{
                                r: 5,
                                stroke: lineColor,
                                fill: 'var(--color-bg-card)',
                                strokeWidth: 2,
                            }}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
