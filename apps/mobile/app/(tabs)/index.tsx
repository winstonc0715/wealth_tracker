/**
 * 總覽 Tab - Mobile Dashboard
 *
 * 手機端最佳化的總覽頁面，支援 Pull-to-refresh。
 */

import React, { useEffect, useCallback } from 'react';
import {
    View,
    Text,
    ScrollView,
    RefreshControl,
    StyleSheet,
    Dimensions,
    TouchableOpacity,
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { usePortfolioStore } from '@/stores/portfolio-store';

const screenWidth = Dimensions.get('window').width;

// 模擬歷史淨值資料
const MOCK_DATA = {
    labels: ['', '', '', '', '', '', ''],
    datasets: [{
        data: [1520000, 1540000, 1500000, 1580000, 1620000, 1590000, 1650000],
        color: (opacity = 1) => `rgba(99, 102, 241, ${opacity})`,
        strokeWidth: 2,
    }],
};

export default function DashboardTab() {
    const {
        summary,
        allocations,
        isLoading,
        displayCurrency,
        exchangeRate,
        fetchPortfolios,
        setDisplayCurrency,
        refreshAll
    } = usePortfolioStore();

    useEffect(() => {
        fetchPortfolios();
    }, []);

    const onRefresh = useCallback(async () => {
        await refreshAll();
    }, [refreshAll]);

    const formatCurrency = (value: number, originalCurrency: string = 'TWD') => {
        let num = Number(value || 0);
        let prefix = 'NT$ ';

        if (displayCurrency === 'USD') {
            num = num / exchangeRate;
            prefix = '$ ';
        }

        return `${prefix}${num.toLocaleString('zh-TW', {
            minimumFractionDigits: displayCurrency === 'USD' ? 2 : 0,
            maximumFractionDigits: displayCurrency === 'USD' ? 2 : 1,
        })}`;
    };

    const pnl = Number(summary?.total_unrealized_pnl || 0);
    const isProfit = pnl >= 0;

    return (
        <ScrollView
            style={styles.container}
            refreshControl={
                <RefreshControl
                    refreshing={isLoading}
                    onRefresh={onRefresh}
                    tintColor="#6366f1"
                    title="更新報價中..."
                    titleColor="#8888aa"
                />
            }
        >
            {/* 幣別切換按鈕 */}
            <View style={styles.topBar}>
                <TouchableOpacity
                    style={[styles.currencyBtn, displayCurrency === 'TWD' && styles.currencyBtnActive]}
                    onPress={() => setDisplayCurrency('TWD')}
                >
                    <Text style={[styles.currencyBtnText, displayCurrency === 'TWD' && styles.currencyBtnTextActive]}>TWD</Text>
                </TouchableOpacity>
                <TouchableOpacity
                    style={[styles.currencyBtn, displayCurrency === 'USD' && styles.currencyBtnActive]}
                    onPress={() => setDisplayCurrency('USD')}
                >
                    <Text style={[styles.currencyBtnText, displayCurrency === 'USD' && styles.currencyBtnTextActive]}>USD</Text>
                </TouchableOpacity>
            </View>

            {/* 淨值摘要卡片 */}
            <View style={styles.summaryCard}>
                <Text style={styles.summaryLabel}>當前淨值</Text>
                <Text style={styles.summaryValue}>
                    {formatCurrency(summary?.net_worth || 0)}
                </Text>
                <View style={styles.pnlRow}>
                    <Text style={[styles.pnlText, isProfit ? styles.pnlUp : styles.pnlDown]}>
                        {isProfit ? '▲' : '▼'} {formatCurrency(Math.abs(pnl))}
                    </Text>
                    <Text style={[styles.pnlBadge, isProfit ? styles.badgeUp : styles.badgeDown]}>
                        {isProfit ? '+' : ''}{((pnl / (Number(summary?.total_assets || 1))) * 100).toFixed(2)}%
                    </Text>
                </View>
            </View>

            {/* 迷你走勢圖 */}
            <View style={styles.chartCard}>
                <Text style={styles.cardTitle}>淨值走勢</Text>
                <LineChart
                    data={MOCK_DATA}
                    width={screenWidth - 64}
                    height={180}
                    chartConfig={{
                        backgroundColor: '#16163a',
                        backgroundGradientFrom: '#16163a',
                        backgroundGradientTo: '#16163a',
                        color: (opacity = 1) => `rgba(99, 102, 241, ${opacity})`,
                        labelColor: () => '#555577',
                        propsForDots: { r: '0' },
                        propsForBackgroundLines: {
                            stroke: 'rgba(42, 42, 90, 0.5)',
                            strokeDasharray: '3 3',
                        },
                    }}
                    bezier
                    withDots={false}
                    withVerticalLabels={false}
                    style={{ borderRadius: 12 }}
                />
            </View>

            {/* 統計數字 */}
            <View style={styles.statsRow}>
                <View style={styles.statItem}>
                    <Text style={styles.statLabel}>總資產</Text>
                    <Text style={styles.statValue}>{formatCurrency(summary?.total_assets || 0)}</Text>
                </View>
                <View style={styles.statItem}>
                    <Text style={styles.statLabel}>總負債</Text>
                    <Text style={[styles.statValue, { color: '#ef4444' }]}>
                        {formatCurrency(summary?.total_liabilities || 0)}
                    </Text>
                </View>
            </View>

            {/* 資產配置 */}
            <View style={styles.chartCard}>
                <Text style={styles.cardTitle}>資產配置</Text>
                {(allocations?.allocations || []).map((item, index) => (
                    <View key={index} style={styles.allocationItem}>
                        <View style={styles.allocationLeft}>
                            <View style={[styles.colorDot, { backgroundColor: item.color || '#6366f1' }]} />
                            <Text style={styles.allocationName}>{item.category}</Text>
                        </View>
                        <View style={styles.allocationRight}>
                            <Text style={styles.allocationValue}>{formatCurrency(Number(item.value))}</Text>
                            <Text style={styles.allocationPct}>{Number(item.percentage).toFixed(1)}%</Text>
                        </View>
                    </View>
                ))}
                {(!allocations || allocations.allocations.length === 0) && (
                    <Text style={styles.emptyText}>暫無配置資料</Text>
                )}
            </View>

            {/* 持倉一覽 */}
            <View style={styles.chartCard}>
                <Text style={styles.cardTitle}>持倉一覽</Text>
                {(summary?.positions || []).map((pos, i) => {
                    const positionPnl = Number(pos.unrealized_pnl);
                    const positionUp = positionPnl >= 0;
                    return (
                        <View key={i} style={styles.positionItem}>
                            <View>
                                <Text style={styles.positionSymbol}>{pos.symbol}</Text>
                                <Text style={styles.positionName}>{pos.name || pos.category_slug}</Text>
                            </View>
                            <View style={{ alignItems: 'flex-end' }}>
                                <Text style={styles.positionValue}>{formatCurrency(Number(pos.total_value))}</Text>
                                <Text style={[styles.positionPnl, positionUp ? styles.pnlUp : styles.pnlDown]}>
                                    {positionUp ? '+' : ''}{Number(pos.unrealized_pnl_pct).toFixed(2)}%
                                </Text>
                            </View>
                        </View>
                    );
                })}
                {(!summary || summary.positions.length === 0) && (
                    <Text style={styles.emptyText}>尚無持倉，請新增交易</Text>
                )}
            </View>

            <View style={{ height: 32 }} />
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#0a0a1a',
        padding: 16,
    },
    summaryCard: {
        backgroundColor: '#16163a',
        borderRadius: 16,
        padding: 24,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#2a2a5a',
        alignItems: 'center',
    },
    topBar: {
        flexDirection: 'row',
        justifyContent: 'flex-end',
        gap: 8,
        marginBottom: 12,
    },
    currencyBtn: {
        paddingHorizontal: 12,
        paddingVertical: 4,
        borderRadius: 8,
        backgroundColor: '#111128',
        borderWidth: 1,
        borderColor: '#2a2a5a',
    },
    currencyBtnActive: {
        backgroundColor: '#6366f1',
        borderColor: '#6366f1',
    },
    currencyBtnText: {
        color: '#8888aa',
        fontSize: 12,
        fontWeight: 'bold',
    },
    currencyBtnTextActive: {
        color: 'white',
    },
    summaryLabel: {
        color: '#8888aa',
        fontSize: 14,
        marginBottom: 4,
    },
    summaryValue: {
        color: '#f0f0ff',
        fontSize: 32,
        fontWeight: '800',
        fontVariant: ['tabular-nums'],
    },
    pnlRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
        marginTop: 8,
    },
    pnlText: {
        fontSize: 14,
        fontWeight: '600',
    },
    pnlUp: { color: '#22c55e' },
    pnlDown: { color: '#ef4444' },
    pnlBadge: {
        paddingHorizontal: 8,
        paddingVertical: 2,
        borderRadius: 6,
        fontSize: 13,
        fontWeight: '600',
        overflow: 'hidden',
    },
    badgeUp: {
        backgroundColor: 'rgba(34, 197, 94, 0.15)',
        color: '#22c55e',
    },
    badgeDown: {
        backgroundColor: 'rgba(239, 68, 68, 0.15)',
        color: '#ef4444',
    },
    chartCard: {
        backgroundColor: '#16163a',
        borderRadius: 16,
        padding: 20,
        marginBottom: 16,
        borderWidth: 1,
        borderColor: '#2a2a5a',
    },
    cardTitle: {
        color: '#f0f0ff',
        fontSize: 16,
        fontWeight: '600',
        marginBottom: 16,
    },
    statsRow: {
        flexDirection: 'row',
        gap: 12,
        marginBottom: 16,
    },
    statItem: {
        flex: 1,
        backgroundColor: '#16163a',
        borderRadius: 12,
        padding: 16,
        borderWidth: 1,
        borderColor: '#2a2a5a',
    },
    statLabel: {
        color: '#8888aa',
        fontSize: 13,
        marginBottom: 4,
    },
    statValue: {
        color: '#f0f0ff',
        fontSize: 18,
        fontWeight: '700',
        fontVariant: ['tabular-nums'],
    },
    allocationItem: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 10,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(42, 42, 90, 0.5)',
    },
    allocationLeft: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
    },
    colorDot: {
        width: 10,
        height: 10,
        borderRadius: 3,
    },
    allocationName: {
        color: '#f0f0ff',
        fontSize: 14,
    },
    allocationRight: {
        alignItems: 'flex-end',
    },
    allocationValue: {
        color: '#f0f0ff',
        fontSize: 14,
        fontWeight: '600',
        fontVariant: ['tabular-nums'],
    },
    allocationPct: {
        color: '#8888aa',
        fontSize: 12,
        fontVariant: ['tabular-nums'],
    },
    positionItem: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingVertical: 12,
        borderBottomWidth: 1,
        borderBottomColor: 'rgba(42, 42, 90, 0.5)',
    },
    positionSymbol: {
        color: '#f0f0ff',
        fontSize: 15,
        fontWeight: '600',
    },
    positionName: {
        color: '#555577',
        fontSize: 12,
        marginTop: 2,
    },
    positionValue: {
        color: '#f0f0ff',
        fontSize: 14,
        fontWeight: '600',
        fontVariant: ['tabular-nums'],
    },
    positionPnl: {
        fontSize: 13,
        fontWeight: '600',
        marginTop: 2,
    },
    emptyText: {
        color: '#555577',
        textAlign: 'center',
        paddingVertical: 20,
        fontSize: 14,
    },
});
